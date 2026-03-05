import random
import time
import uuid


def uuid7(timestamp: int | None = None, random_bits: int | None = None):
    # log = logging.getLogger("uuid7")
    # Get current time in nanoseconds.
    t_ns = timestamp if timestamp is not None else time.time_ns()
    # Derive the millisecond portion (48 bits).
    ms = t_ns // 1_000_000
    # Derive the sub-millisecond remainder.
    rem = t_ns % 1_000_000
    # Map the remainder into 12 bits (0–4095).
    sub_ms = (rem * 4096) // 1_000_000
    # Build the 64-bit "upper" part:
    #  - Upper 48 bits: ms timestamp.
    #  - Next 4 bits: version (0x7).
    #  - Last 12 bits: sub-millisecond fraction.
    upper = (ms << 16) | ((7 << 12) | sub_ms)

    random_bits = random_bits if random_bits is not None else random.getrandbits(62)
    # Build the 64-bit "lower" part with 2-bit variant (0b10) and 62 random bits.
    lower = (0b10 << 62) | random_bits
    # Combine into a 128-bit integer.
    result = uuid.UUID(int=((upper << 64) | lower))
    # log.debug(f"t_ns        = {t_ns}")
    # log.debug(f"ms          = {ms}")
    # log.debug(f"rem         = {rem}")
    # log.debug(f"sub_ms      = {sub_ms}")
    # log.debug(f"upper       = {upper}")
    # log.debug(f"random_bits = {random_bits}")
    # log.debug(f"lower       = {lower}")
    # log.debug(f"result      = {result}")
    return result
