#!/bin/bash

pywb_ca="/usr/share/ca-certificates/pywb-ca.pem"

if [ -n "$HTTP_PROXY" ] && [ ! -f "${pywb_ca}" ]; then

  echo "Configuring proxy configuration for local development mode"  
  mkdir -p $HOME/.pki/nssdb
  certutil -d $HOME/.pki/nssdb -N --empty-password  
  curl -k https://wsgiprox/download/pem -o /usr/share/ca-certificates/pywb-ca.pem
  cp /usr/share/ca-certificates/pywb-ca.pem /usr/local/share/ca-certificates/CertificateName.pem
  echo  pywb-ca.pem |  tee -a /etc/ca-certificates.conf
  certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n CertificateNickName -i '/usr/local/share/ca-certificates/CertificateName.pem';
  update-ca-certificates --fresh
  
fi

if [ -n "$HTTP_PROXY" ]; then
  export CRIMSONKING_DATA_BUCKET=$(awslocal s3api list-buckets --query "Buckets[*].[Name]" --output text | grep crimson) 
  echo "export MEGAMAID_DATA_BUCKET=$CRIMSONKING_DATA_BUCKET" >/env.sh
  export CRIMSONKING_EXPORT_BUCKET=$CRIMSONKING_DATA_BUCKET
  echo "export MEGAMAID_EXPORT_PREFIX=$CRIMSONKING_DATA_BUCKET" >>/env.sh
  export CRIMSONKING_EXPORT_PREFIX=crimsonking
  echo "export MEGAMAID_EXPORT_PREFIX=$CRIMSONKING_EXPORT_PREFIX" >>/env.sh
    
  chmod +x /env.sh 
  source /env.sh
  env
  curl https://ipinfo.io/json
  echo ""
  echo "please validate proper proxy before continuing"

fi  



if [ -n "$AWS_LAMBDA_FUNCTION_NAME" ]; then
  echo "Running inside an AWS Lambda function."
  /usr/bin/python -m awslambdaric crimsonking_downloader.interface.aws.lambda.lambdahandler.handler
else   
  echo "Not running inside an AWS Lambda function."
  /.aws-lambda-rie/aws-lambda-rie /usr/bin/python -m awslambdaric crimsonking_downloader.interface.aws.lambda.lambdahandler.handler 
#  /.aws-lambda-rie/aws-lambda-rie /usr/bin/python -m awslambdaric megamaid_download.interface.aws.lambdahandlers.handle_crawl &
#   count=0
#   while [ $count -lt 5 ]; do
#     wait 1
#     curl "http://localhost:8080/2015-03-31/functions/function/invocations" -d '{}'
#     if [ $? -eq 0 ]; then
#       echo "Command successful, exiting loop."
#       break
#     fi
#     echo "Command failed, continuing loop."
#     count=$((count + 1))
#   done

  
fi
