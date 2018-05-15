from collections import OrderedDict
import datetime
import requests
import xmltodict

BOE_BARE_BASE_URL = 'http://boe.es'
BOE_BASE_URL = f'{BOE_BARE_BASE_URL}/diario_boe/xml.php?id=BOE-'
words = ['Víctor']


def get_boe_url(date=None):
    if date is None:
        date = datetime.datetime.now()
    elif type(date) is float or type(date) is int:
        date = datetime.datetime.fromtimestamp(date)
    elif type(date) is not datetime.datetime:
        date = datetime.datetime.strptime(date, '%Y%m%d')
    date_str = date.strftime('%Y%m%d')
    return BOE_BASE_URL + 'S-' + date_str


def parse_boe(boe_text):
    def scrap(data):
        out_list = []
        if type(data) is list:
            for each in data:
                out_list += scrap(each)
        elif type(data) is OrderedDict:
            if 'urlXml' in data:
                out_list += [{data['titulo']: data['urlXml']}]
            else:
                for val in data.values():
                    out_list += scrap(val)
        else:
            pass

        return out_list

    raw_dict = xmltodict.parse(boe_text)
    scraped = scrap(raw_dict)
    out_dict = {}
    for each in scraped:
        out_dict[[*each][0]] = each[[*each][0]].split('/diario_boe/xml.php?id=BOE-')[1]
    return out_dict


def scrap_boe_items(boe_dict):
    out_dict = {}
    for each in boe_dict:
        url = BOE_BASE_URL + boe_dict[each]
        data = requests.get(url).text
        out_dict[each] = {
            'url': url,
            'data': data,
            'pdf': f'{BOE_BARE_BASE_URL}{data.split("<url_pdf>")[1].split("</url_pdf>")[0]}'
        }
    return out_dict


def search_words_in_boe(words, boe_items):
    appearances = {}
    for name in boe_items:
        item = boe_items[name]
        for word in words:
            if word in item['data']:
                if 'name' not in appearances:
                    appearances[name] = []
                appearances[name] += [word]

    return appearances
