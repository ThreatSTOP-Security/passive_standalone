import configparser
import logging
import ipaddress
import re
import tldextract


def set_logger(debug=False, silence_requests=True):
    """
    This function creates a logger with the correct format and returns it
    :param silence_requests: Sets requests logger to warning.
    :param debug: boolean, if true the logger logs debug messages as well
    :return: a logger object
    """
    config = configparser.RawConfigParser()
    config.read('config.cfg')

    if silence_requests:
        logging.getLogger("requests").setLevel(logging.WARNING)  # Silencing annoying Requests log info.

    logger = logging.getLogger("logger")

    if debug:
        logger.setLevel(logging.DEBUG)

    else:
        logger.setLevel(logging.INFO)

    log_format = str(config.get('LOG', 'format'))
    formatter = logging.Formatter(log_format)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def is_ip(ip, public=True):
    """
    Gets a string checks if its an valid IP address if `public` flag is on it checks that the address isn't reserved
    or private.
    :param public: Boolean Flag, cif True the IP is tested to be a public one.
    :param ip: string representation of an IP address
    :return: True if the string is a valid IP address
    """

    try:
        temp = ipaddress.ip_address(ip)

    except ValueError:
        return False

    if public:
        if temp.is_reserved or temp.is_private:
            return False

        else:
            return True

    else:
        return True


def is_valid_domain(domain):
    """
    The function checks if a given domain is valid
    :param domain: a domain as a string
    :return: True if its valid False if not
    """

    domain = tldextract.extract(domain)
    valid = re.compile(r'^[a-zA-Z\d-]{,63}(\.[a-zA-Z\d-]{,63})*$')

    if domain.suffix and domain.domain and re.match(valid, domain.suffix + domain.domain):
        return True

    else:
        return False
