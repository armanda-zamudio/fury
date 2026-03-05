from __future__ import annotations
import re
import uuid
import boto3
import random
import logging
import typing
import string
import random
import requests
import threading
from enum import StrEnum
from pynamodb.models import Model
from pynamodb.attributes import (
    BooleanAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
    ListAttribute,
    NumberAttribute
)
from pynamodb.indexes import(
    GlobalSecondaryIndex,
    AllProjection
)
from datetime import datetime, timedelta, timezone
from functools import singledispatchmethod

from proxy.domain.ports import ProxyStore
from ih.download.domain.model import ProxyUrl
from ih.download.domain.ports import ProxyUrlFactory



class MarsProxyUrlFactory(ProxyUrlFactory):
    def __init__(self):
        self._log = logging.getLogger().getChild(self.__class__.__qualname__)

    def _test_and_persist(self,country:str,proxy_url:str) ->bool:
        try:
            self._log.info("Attempting to test connection...")
            tmp = [member for member in IPInfo if country.lower() in member.name.lower() ]
            if tmp:
                ip_info = tmp[0]
            else:
                ip_info = IPInfo.IP_INFO
            self._log.info(f"Using the following info connection for country {country.upper()}: {ip_info}")
            proxy_ip_info = ProxyIPInfo(ip_info)
            proxy_ip_info.invoke_ip_info(proxy_url)
            ProxyTable.store_connection_by_proxyipinfo_threaded(ipinfo=proxy_ip_info,domain="UNKNOWN",country_city=None)
        except:
            self._log.info("could not connect to or persist proxy URL")
            return False
        return True
    
    def _test_and_persist_threaded(self,country:str,proxy_url:str):
        
        thread = threading.Thread(target=self._test_and_persist, args=(country,proxy_url))
        thread.start()
        return thread
                    

    def __call__(
        self,
        *,
        username: str,
        password: str,
        hostname: str = "ultra.marsproxies.com",
        port: int = 44443,
        location: tuple[str, str] | None = None,
        session: tuple[str, str] | None = None,
        persist: bool = True
    ) -> ProxyUrl:
        fields = {}
        if location:
            fields["country"] = location[0]
            if  location[1]:
                fields["city"] = location[1]
        if session:
            fields["session"] = session[0]
            fields["lifetime"] = session[1]

        pieces = [
            password,
            *[f"{field}-{value}" for (field, value) in fields.items() if bool(value)],
        ]
        auth = "_".join(pieces)
        result = f"http://{username}:{auth}@{hostname}:{port}"
        self._log.info(
            f"Build proxy url {result.replace(username, 'XXXXXXXX').replace(password, 'XXXXXXXX')}"
        )
        if persist and location:
            self._test_and_persist_threaded(country=location[0],proxy_url=result)
            # for i in range(3):
            #     if self._test_and_persist(country=location[0],proxy_url=result):
            #         return result
            # raise IPInfoError("Could not establish connection using proxy URL")
        return result
    
    @staticmethod
    def create_random_session():
        alpha = string.ascii_lowercase + string.digits
        return "".join(random.choices(alpha, k=8))
    
    @staticmethod
    def clean_url(url:ProxyUrl) ->ProxyUrl:
        pattern = r"(/)(.*?)(_)"
        new_string = "/XXXXXXXX:XXXXXXXX"
        result = re.sub(pattern, r"\1" + new_string + r"\3", url)
        return result    
    
    @staticmethod
    def add_user_pass_to_url(url:ProxyUrl, creds:str) -> ProxyUrl:
        hidden_creds = "XXXXXXXX:XXXXXXXX"
        return url.replace(hidden_creds,creds)

class RandomMarsProxyUrlFactory(ProxyUrlFactory):
    def __init__(
        self,
        *,
        username: str,
        password: str,
        locations: typing.Iterable[typing.Tuple[str, typing.Iterable[str]]] = [
            # ("us", ("ashburn"))
        ],        
        lifetimes: typing.Iterable[str] | None = ["30m"],
        hostname: str = "ultra.marsproxies.com",
        port: int = 44443,
        persist:bool = True        
    ):
        self._username          = username
        self._password          = password
        self._locations         = locations
        self._lifetimes         = lifetimes
        self._hostname          = hostname
        self._port              = port
        self._persist           = persist        
        self._log               = logging.getLogger().getChild(self.__class__.__qualname__)
    

    def populate_user_pass_from_ssm(self, ssm_credential_path:str, boto_session: boto3.Session | None = None):
        # if self._username and self._password and self._ssm_credentials:
        if self._username and self._password:
            self._log.info("Credentials were previously set")
            return
        # expecting value to be store in the following patter: Username:Password
        self._load_string_parameter(ssm_credential_path, boto_session)
        username, password = self._load_string_parameter(ssm_credential_path, boto_session).split(":",1)
        self._username = username
        self._password = password

    def populate_location_from_ssm(self,ssm_location_path:str, country_code:str, boto_session: boto3.Session | None = None):
        if self._locations:
            self._log.info("Location was previously set")
            return
        tmp_cities_var:str = self._load_string_parameter(ssm_location_path, boto_session)
        if "," in tmp_cities_var:
            proxy_cities:list[str] = tmp_cities_var.split(",")
        else:
            proxy_cities = [tmp_cities_var]
        self._locations = [(country_code, proxy_cities)]
        
    def _load_string_parameter(self, name: str, boto_session: boto3.Session | None = None) -> str:
        session = boto_session or boto3.Session()
        ssm_client = session.client("ssm")
        parameter_response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        parameter = parameter_response["Parameter"]
        return parameter["Value"]	

    def _create_random_session(self):
        alpha = string.ascii_lowercase + string.digits
        return "".join(random.choices(alpha, k=8))
        

    def __call__(self) -> ProxyUrl:
        self._log.info(
            f"Using proxy username {self._username[:3]}XXXXXXXX{self._username[-1]}"
        )
        self._log.info(
            f"Using proxy password {self._password[:3]}XXXXXXXX{self._password[-1]}"
        )
        country, cities = random.choice(self._locations)
        self._log.info(f"Using country {country}")
        if cities:
            city = random.choice(cities)
            self._log.info(f"Using city {city}")
        else:
            city = None
            self._log.info("Not using city")
        
        location = (country, city)
        if self._lifetimes:
            session = (self._create_random_session(), random.choice(self._lifetimes))
        else:
            session = None
        return MarsProxyUrlFactory()(
            username=self._username,
            password=self._password,
            hostname=self._hostname,
            port=self._port,
            location=location,
            session=session,
            persist=self._persist
        )  
    
    @staticmethod
    def clean_url(url:ProxyUrl) ->ProxyUrl:
        return MarsProxyUrlFactory.clean_url(url)

class IPInfoError(Exception):... 

class IPInfo(StrEnum):
    IP_INFO     = "https://ipinfo.io/json"
    IP_CN_IR    = "http://ip-api.com/json"
    # IP_IR   = "http://ip-api.com/json"
    # IP_CN   = "https://my.ip.cn/json/" # Currently this endpoint is not functioning
    


class ProxyIPInfo:
    ip:str          = None
    city:str        = None
    region:str      = None
    country:str     = None
    loc:str         = None
    org:str         = None
    time_zone:str   = None
    message:str     = None
    proxy_url       = None
    def __init__(self,info_url:IPInfo):
        self._log = logging.getLogger().getChild(self.__class__.__qualname__)
        self.info_url = info_url    
    def invoke_ip_info(self,proxy_url:ProxyUrl|str = ""):
        self._log.info(f"Invoking URL: {self.info_url}")
        self.proxy_url = proxy_url
        _proxies = {
            "http": proxy_url,
            "https":proxy_url
        }
        ip_info_url:IPInfo = self.info_url
        response = None
        try:
            response = requests.get(ip_info_url,proxies=_proxies, verify=False, timeout=5)
            response_json = response.json()
        except:
            self._log.error(f"ERROR: {response}")             
            if ip_info_url is not IPInfo.IP_INFO:
                self._log.info(f"retrying with the following ip info url {IPInfo.IP_INFO:}")
                ip_info_url = IPInfo.IP_INFO
                response = requests.get(ip_info_url,proxies=_proxies, verify=False, timeout=5)
                response_json = response.json()
            else:
                raise

        self._log.info(f"IP INFO: {response_json}")
        match ip_info_url:
            case IPInfo.IP_INFO:                
                self.ip = response_json["ip"]
                self.city = response_json["city"]
                self.region = response_json["region"]
                self.country = response_json["country"]
                self.loc = response_json["loc"]
                self.org = response_json["org"]
                self.time_zone = response_json["timezone"]
                self.message = str(response_json)

            case IPInfo.IP_CN_IR:
                self.ip = response_json["query"]
                self.city = response_json["city"]
                self.region = response_json["regionName"]
                self.country = response_json["countryCode"]
                self.loc = f"lat:{response_json["lat"]},lon:{response_json["lon"]}" 
                self.org = response_json["org"]
                self.time_zone = response_json["timezone"]
                self.message = str(response_json)
        return response_json


    def __str__(self):
        if self.message:
            return f"Current proxy connection metadata: {self.message}"
        else:
            return ""


        # def __call__(self):

class CountryCityIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "country_city-index"
        projection = AllProjection()
    country_city = UnicodeAttribute(hash_key=True)
    expiration_time = UTCDateTimeAttribute(range_key=True)

class DomainIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "domain-index"
        projection = AllProjection()
    domain = UnicodeAttribute(hash_key=True)
    expiration_time = UTCDateTimeAttribute(range_key=True)

class IPIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "ip-index"
        projection = AllProjection()
    ip = UnicodeAttribute(hash_key=True)
    expiration_time = UTCDateTimeAttribute(range_key=True)    

class ExpireIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "expire-index"
        projection = AllProjection()
    has_expired = UnicodeAttribute(hash_key=True)
    expiration_time = UTCDateTimeAttribute(range_key=True)       

class DomainProxyTable(Model):
    class Meta:
        table_name = "DOMAIN_PROXY_TABLE"
        region = "us-east-1"
        # host = "http://localhost:4566"
    domain = UnicodeAttribute(hash_key=True)
    url = UnicodeAttribute()
    health_url = UnicodeAttribute(null=True)
    session_duration = UnicodeAttribute(default=timedelta(minutes=30))
    session_number = NumberAttribute(default=3)
    ip_info_url = UnicodeAttribute(default=IPInfo.IP_INFO)
    valid_proxy_cities = ListAttribute(of=UnicodeAttribute,default=list)


class ProxyTable(Model):    
    _log = logging.getLogger().getChild(__qualname__)
    class Meta:
        table_name = "PROXY_TABLE"
        region = "us-east-1"
        # host = "http://localhost:4566"
    uuid = UnicodeAttribute(hash_key=True,default=str(uuid.uuid4()))
    country_city = UnicodeAttribute()
    domain = UnicodeAttribute()
    tags = ListAttribute(of=UnicodeAttribute,default=list)    
    proxy_connection = UnicodeAttribute()
    create_date = UTCDateTimeAttribute(default=datetime.now(timezone.utc))
    ip = UnicodeAttribute(default="0.0.0.0")
    expiration_time = UTCDateTimeAttribute(range_key=True, default=lambda: datetime.now(timezone.utc) + timedelta(minutes=30))
    metadata = UnicodeAttribute(null=True)
    has_expired = UnicodeAttribute(default="false")
    proxy_connection_in_use = BooleanAttribute(default=False)
    country_city_index = CountryCityIndex()
    domain_index = DomainIndex()
    ip_index = IPIndex()
    expire_index = ExpireIndex()

    # @singledispatchmethod
    @staticmethod
    def store_connection(country_city, proxy_connection, domain, tags = [], ip = None) ->ProxyTable:
        ProxyTable._log.info("running populate")
        proxy = ProxyTable(country_city=country_city,
                           domain = domain,
                           tags = tags,
                           proxy_connection = proxy_connection,                        
                           ip = ip
                           )
        proxy.save()        
        ProxyTable._log.info(proxy)
        return proxy

    # @store_connection.register
    @staticmethod    
    def store_connection_by_proxyipinfo(ipinfo:ProxyIPInfo,domain:DomainProxyTable|str,country_city:str|None=None)->ProxyTable:        
        _country_city = None
        if country_city:
            _country_city = country_city
        else:
            _country_city = f"{ipinfo.country.lower()}_{ipinfo.city.lower()}"

        _domain = None
        if isinstance(domain,DomainProxyTable):
            _domain = domain.domain
        else:
            _domain = domain

        
        
        proxy = ProxyTable(uuid=str(uuid.uuid4()),
                        country_city=_country_city,
                        tags = [_country_city,_domain],
                        proxy_connection = RandomMarsProxyUrlFactory.clean_url(ipinfo.proxy_url), 
                        domain = _domain,                       
                        ip = ipinfo.ip,
                        metadata = ipinfo.message,
                        proxy_connection_in_use = True
                        )   
        
        proxy.save()
        ProxyTable._log.info(proxy)
        return proxy
    
    @staticmethod
    def store_connection_by_proxyipinfo_threaded(ipinfo:ProxyIPInfo,domain:DomainProxyTable|str,country_city:str|None=None):        
        thread = threading.Thread(target=ProxyTable.store_connection_by_proxyipinfo, args=(ipinfo,domain,country_city))
        thread.start()
        return thread
        # with concurrent.futures.ThreadPoolExecutor() as executer:
        #     future = executer.submit(ProxyTable.store_connection_by_proxyipinfo, ipinfo,domain,country_city)
        #     return future
        


    @staticmethod
    def query_country_city(value)->list[ProxyTable]:        
        results:list[ProxyTable] = list(ProxyTable.country_city_index.query(value))        
        ProxyTable._log.debug(results)
        return results
    
    @staticmethod
    def query_domain(value)->list[ProxyTable]:        
        domains:list[ProxyTable] = list(ProxyTable.domain_index.query(value))
        ProxyTable._log.debug(domains)
        return domains
    
    @staticmethod
    def query_tag(value)->list[ProxyTable]:
        tags:list[ProxyTable] = list(ProxyTable.scan(ProxyTable.tags.contains(value)))
        ProxyTable._log.debug(tags)
        return tags

    @staticmethod
    def get_connection_by_domain(domain) ->ProxyTable:
        results = list(ProxyTable.domain_index.query(domain, 
                                      filter_condition=ProxyTable.has_expired.contains("false") 
                                                       & ProxyTable.proxy_connection_in_use.contains(False)))
        if results:
            random_connection:ProxyTable|None = random.choice(results)        

            if random_connection:
                ProxyTable._log.debug(random_connection.proxy_connection)                
                random_connection.proxy_connection_in_use = "True"
                random_connection.save()
                return random_connection
            else:
                print("No connections available")
                return None
        return None  
    
    @staticmethod
    def get_valid_connections() ->list[ProxyTable]:
        results = list(ProxyTable.expire_index.query("false"))
        return results

    @staticmethod
    def get_ip_count(ip):
        ips = ProxyTable.get_by_ip(ip)
        ProxyTable._log.info(f"Total Count of IP: {len(ips)}")
        ProxyTable._log.debug(ips)
        return len(ips)    
    @staticmethod
    def get_by_ip(ip)->list[ProxyTable]:
        ips:list[ProxyTable] = list(ProxyTable.ip_index.query(ip))
        ProxyTable._log.debug(ips)
        return ips
    
    @staticmethod
    def reset_connection(uuid):
        connection:list[ProxyTable]|None = list(ProxyTable.query(uuid))
        for con in connection:
            con.proxy_connection_in_use = "False"
            con.save()      
            ProxyTable._log.info(f"Reset the following connection: {con}")
        
