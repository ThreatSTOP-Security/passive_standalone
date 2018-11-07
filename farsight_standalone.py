import argparse
import configparser
import json

import requests
import tldextract

from passive_standalone.createexcel import CreateExcel
from passive_standalone.utils import is_ip, is_valid_domain, set_logger

__author__ = 'Dror Avrahami'
__version__ = '0.03'

# Change Log:
# ----------
# 2018-10-18    0.01    Created
# 2018-10-21    0.02    Added a limit argument, some comments and a simple text output. [Dror Av]
# 2018-10-28    0.03    Simple output now also prints number of resolutions. [Dror Av]


class FarSightError(Exception):
    """
    Just a general Exception
    """

    pass


class FarSight(object):
    """
    Uses Farsight DB to check for resolutions
    """

    def __init__(self):
        """
        Init for Farsight module. Sets up class with passed parameters and some constants
        """

        self.config = configparser.ConfigParser()
        self.config.read('config.cfg')
        self.key = self.config.get('FARSIGHT', 'key')
        self.url = self.config.get('FARSIGHT', 'url')
        self.sec_per_day = 86400  # Amount of seconds per day

        self.headers = {'X-API-Key': self.key, 'Accept': 'application/json'}
        self.logger = set_logger()
        self.periods = [7]

    def run(self, data, periods=None, excel=True, max_tlds=10, path='c:/analysis/', limit=4000000):
        """
        Main metod.
        :param data: The IOCs passed by the user (list of string)
        :param periods: Periods to check (list of int)
        :param excel: If true an excel file will be created (Boolean)
        :param max_tlds: Amount of top TLDs to print, default is 10. (int)
        :param path: The path in which the file will be saved. (str)
        :param limit: Limit Number of results to return by the API, default is 4M (int)
        :return: All the data in a dictionary form.
        """

        if periods:
            self.periods = periods

        self.logger.info('Running Farsight pDNS module')

        final_output = []

        for raw_ioc in data:
            temp = {'ioc': raw_ioc}

            for days in self.periods:
                try:
                    if is_ip(raw_ioc):
                        # Runs rdata query.
                        temp[days] = {'rdata': self.rdata(raw_ioc.replace("/", ","), "ip", days=days, limit=limit)}

                    elif is_valid_domain(raw_ioc):
                        # Runs both rdata and rrset
                        temp[days] = {'rrset': self.rrset(raw_ioc, days=days)}
                        temp[days] = {'rdata': self.rdata(raw_ioc, "name", days=days, limit=limit)}

                    else:
                        self.logger.error('Not a valid IP - {}'.format(raw_ioc))
                        continue

                except FarSightError:
                    self.logger.debug('No Data for {} due to error'.format(raw_ioc))
                    continue

                self._parse_data(temp[days])
                self.logger.debug('Resolved {}'.format(raw_ioc))

            final_output.append(temp)

        self.logger.info('Done')

        if excel:
            excel = CreateExcel()
            excel.run(final_output, max_tlds=max_tlds, periods=self.periods)
            excel.save_workbook(path)

        return final_output

    def _query(self, command, ioc, parameter):
        """
        Make the actual GET request and parses the response
        :param command: DNSDB API command
        :param ioc: The IOC for the query
        :return: Returns a JSON
        """
        response_codes = {400: 'URL is formatted incorrectly',
                          403: 'X-API-Key header is not present, or the provided API key is not valid',
                          404: 'No records found for the given lookup',
                          429: 'API key daily quota limit is exceeded',
                          500: 'Error processing the request',
                          503: 'The limit of number of concurrent connections is exceeded'}

        try:
            response = requests.get(self.url + command, headers=self.headers, params=parameter)
            response.raise_for_status()

        except requests.HTTPError:
            self.logger.debug('No Results Found For - {}'.format(ioc))
            return '{} ({} Days)'.format(response_codes[response.status_code],
                                         parameter['time_last_after'] * -1 / self.sec_per_day)

        return self._parse_response(response)

    def _parse_response(self, response):
        """
        Parses the GET response.
        :param response: Response for the GET request sent to DNSDB.
        :return: A Parsed answer
        """

        json_response = response.text.split('\n')
        return [json.loads(answer) for answer in json_response if answer]

    def rdata(self, ioc, ioc_type, days, limit):
        """
        The "rdata" lookup queries DNSDB's Rdata index, which supports "inverse" lookups based on Rdata record values.
        In contrast to the rrset lookup method, rdata lookups return only individual resource records and not full
        resource record sets, and lack bailiwick metadata. An rrset lookup on the owner name reported via an rdata
        lookup must be performed to retrieve the full RRset and bailiwick.
        :param limit: API results limit.
        :param days: amount of days to check.
        :param ioc_type: Either `name` for domains or `ip` for IPs.
        :param ioc: The IOC to query.
        """

        parameter = {'time_last_after': self.sec_per_day * -1 * days,
                     'limit': limit}

        command = 'lookup/rdata/{ioc_type}/{query}'.format(ioc_type=ioc_type, query=ioc)

        domains = self._query(command, ioc, parameter)

        return domains

    def rrset(self, ioc, days):
        """
        The "rrset" lookup queries DNSDB's RRset index, which supports "forward" lookups based on the owner name
        of an RRset.
        :param days: amount of days to check.
        :param ioc: The IOC to query
        """

        parameter = {'time_last_after': self.sec_per_day * -1 * days}

        command = 'lookup/rrset/name/{query}'.format(query=ioc)

        return self._query(command, ioc, parameter)

    def _parse_data(self, iocs):
        # Counts unique TLDs and domains in the IP.

        iocs['top_lvl_domains'] = {}
        iocs['second_lvl_domains'] = {}

        for data in iocs['rdata']:
            parse = tldextract.extract(data['rrname'])

            try:
                iocs['top_lvl_domains'][parse.suffix] += 1

            except KeyError:
                iocs['top_lvl_domains'][parse.suffix] = 1

            try:
                iocs['second_lvl_domains'][parse.registered_domain] += 1

            except KeyError:
                iocs['second_lvl_domains'][parse.registered_domain] = 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gives data about TLDs and Host-Names in a specific IP",
                                     fromfile_prefix_chars='@')
    parser.add_argument("ips", nargs='+', help="List of IPs to check")
    parser.add_argument("-p", "--path", type=str, dest="path", default='c:/analysis/',
                        help="Path to save the excel file")
    parser.add_argument("-d", "--periods", type=int, nargs="+", dest="periods", default=[7, 90],
                        help="The Script will check top TLDs and tod host-name for each period")
    parser.add_argument("-t", "--top_amount", type=int, dest="top", default=10,
                        help="How many top TLDs to display in the spreadsheet")
    parser.add_argument("-l", "--limit", type=int, dest="limit", default=4000000,
                        help="How many results will be returned - default is max, 4,000,000")
    parser.add_argument("-e", "--excel", action='store_false', default=True,
                        help="Don't save an Excel spreadsheet")
    args = parser.parse_args('209.99.40.222 198.57.247.217 -l 10000 -d 7 30 90'.split())

    dnsdb = FarSight()
    output = dnsdb.run(data=args.ips,
                       path=args.path,
                       periods=args.periods,
                       max_tlds=args.top,
                       excel=args.excel,
                       limit=args.limit)

    if args.excel:
        print('\nFull breakdown saved to - "{}"\n'.format(args.path))

    print('Max Resolutions: {}\n'.format(args.limit))

    for ioc in output:
        print('IP - {}'.format(ioc['ioc']))
        print('-' * len('IP - {}'.format(ioc['ioc'])))
        ioc.pop('ioc')

        for period, results in ioc.items():
            resolutions = len(results['rdata'])
            tlds = results['top_lvl_domains']
            top_tld = max(tlds.keys(), key=(lambda key: tlds[key]))  # Finds most common TLD
            print('{}\tDays: {} Resolutions, {} Unique TLDs, Most Common ".{}"'.format(period, resolutions,
                                                                                       len(tlds), top_tld))

        print()
