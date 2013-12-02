import binascii
import collections
import logging
import os
import urllib
import urllib2
import sys

from bs4 import BeautifulSoup

import MySQLdb

GS_URL = "http://scholar.google.ca/citations"

class GSParser(object):

    def __init__(self, profile_id, page_size=100):
        self.params = {
            'cstart' : 0,
            'hl' : 'en',
            'pagesize' : page_size,
            'sortby' : 'pub_date',
            'user' : profile_id,
            'view_op' : 'list_works',
        }

    def get_profile(self, max_publications):
        page_num = 0
        data = []
        previous_data = None
        all_data = []

        if max_publications <= 0:
            max_publications = sys.maxint

        # Fetch all pages of publications
        while data is not None and data != previous_data and len(all_data) < max_publications:
            previous_data = data
            html = self.get_page(page_num)
            data = self.parse_profile(html)
            for row in data:
                if row not in all_data:
                    all_data.append(row)
                if len(all_data) >= max_publications:
                    return all_data
            if len(data) < self.params['pagesize']:
                return all_data
            page_num += 1

        return all_data

    def get_page(self, page_num=0):
        headers = {
            'User-Agent' : 'Mozilla/5.0',
            'Cookie' : 'GSP=ID=%s' % binascii.b2a_hex(os.urandom(8))
        }
        self.params['cstart'] = page_num * self.params['pagesize']
        request = urllib2.Request(GS_URL + "?" + urllib.urlencode(self.params), headers=headers)
        response = urllib2.urlopen(request)
        html = response.read()
        return html.replace("<br>", "")

    def parse_profile(self, html):
        soup = BeautifulSoup(html)
        all_data = []

        # Find all citation items, store info in dictionary
        i = 0
        for item in soup.find_all("tr", {"class" : "cit-table item"}):
            
            data = {
                'title': '',
                'authors': '',
                'journal': '',
                'citations': '',
                'year': '',
                'citelink': '',
                'citedbylink': '',
            }

            # Determine title, author, and journal from first column
            col1 = item.find("td", {"id" : "col-title"})
            titleauthor = col1.find("a")
            authors = titleauthor.find_next_sibling("span")
            journal = authors.find_next_sibling("span")
            if titleauthor is not None:
                data['title'] = titleauthor.string
                if titleauthor['href'] is not None:
                    data['citelink'] = titleauthor['href']
            if authors is not None:
                data['authors'] = authors.string
            if journal is not None:
                data['journal'] = journal.string

            # Determine number of citations from second column
            col2 = item.find("td", {"id" : "col-citedby"})
            citations = col2.find("a")
            if citations is not None:
                data['citations'] = citations.string
                if citations['href'] is not None:
                    data['citedbylink'] = citations['href']

            # Determine year of publication from third column
            col3 = item.find("td", {"id" : "col-year"})
            if col3 is not None:
                data['year'] = col3.string

            # Strip whitespace
            data = dict(map(lambda (k,v): (k, v.strip() if v is not None else ''), data.iteritems()))

            all_data.append(data)
            i += 1

        return all_data


def save_file(filename, string):
    text_file = open(filename, "w")
    text_file.write(string.encode('utf-8'))
    text_file.close()

def main():

    # Parse command line arguments
    user_id = sys.argv[1]
    profile_id = sys.argv[2]
    max_publications = 0
    if len(sys.argv) >= 4:
        max_publications = int(sys.argv[3])

    # Scrape profile data
    gsp = GSParser(profile_id)
    data = gsp.get_profile(max_publications)

    #Store data in Drupal database
    conn = MySQLdb.connect(
        host= "localhost",
        user="root",
        passwd="stupidPassword8.",
        db="drupaldb",
        use_unicode=True
    )
    conn.set_character_set('utf8')
    cursor = conn.cursor()
    cursor.execute('SET NAMES utf8;')
    cursor.execute('SET CHARACTER SET utf8;')
    cursor.execute('SET character_set_connection=utf8;')

    i = 0
    try:
        cursor.execute("DELETE FROM publications WHERE uid=%s" % user_id)
        for row in data:
            cursor.execute(
                """INSERT INTO publications (uid, title, authors, journal, citations, year, citelink, citedbylink) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, row['title'], row['authors'], row['journal'], row['citations'], row['year'], row['citelink'], row['citedbylink'])
            )
            i += 1
        conn.commit()
    except Exception, e:
        print e
        conn.rollback()

    conn.close()

if __name__ == "__main__":
    main()