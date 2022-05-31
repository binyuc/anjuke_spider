import re
import json
import datetime
from loguru import logger
import requests
from lxml import etree
import time
import random
from utils.mysql_writer import *
from utils.mysql_reader import *
import pandas as pd

user_agent = [
    "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 "
    "Safari/534.50",
    "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:38.0) Gecko/20100101 Firefox/38.0",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; .NET4.0C; .NET4.0E; .NET CLR 2.0.50727; .NET CLR 3.0.30729; "
    ".NET CLR 3.5.30729; InfoPath.3; rv:11.0) like Gecko",
    "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
    "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)",
    "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
    "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
    "Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36"
]
headers = {}
headers['referer'] = 'https://shanghai.anjuke.com/community/pudong/o2/'
# ip_url = 'http://webapi.http.zhimacangku.com/getip?num=1&type=2&pro=&city=0&yys=0&port=11&pack=136329&ts=0&ys=0&cs=0&lb=1&sb=0&pb=4&mr=1&regions='

ip_url = 'https://proxyapi.horocn.com/api/v2/proxies?order_id=OTS91734254532679303&num=20&format=json&line_separator=win&can_repeat=yes&user_token=df2e922b7f4da8feb40a4d5c3cec05d3'


class CrawlSpider(object):
    def __init__(self):
        self.final_res = []
        with open(r'cache/neighbor_list.json', 'r') as fp:
            self.neighbor_list = json.load(fp)

        # logger.add('crawl.log', enqueue=True, retention="10 days", rotation="100 MB", backtrace=True, diagnose=False)

    def ip_pool(self, ip_url):
        """芝麻"""
        try:
            ip_res = requests.get(url=ip_url)
        except:
            logger.error('请重新更新url')
            time.sleep(5)
            ip_res = requests.get(url=ip_url)
        ip_list = []
        proxies_list = []
        for i in ip_res.json()['data']:
            # ip = 'https://' + i['ip'] + ':' + str(i['port'])
            ip = 'http://' + i['host'] + ':' + str(i['port'])
            ip_list.append(ip)
            proxie = {'https': ip}
            proxies_list.append(proxie)
        return proxies_list

    def get_ip(self):
        try:
            proxies_list = self.ip_pool(ip_url)
        except:
            time.sleep(10)
            proxies_list = self.ip_pool(ip_url)
        return proxies_list

    def parse(self, tree):
        for a in tree.xpath('/html/body/div/div/div/section/section[3]/section/div[2]/a'):
            temp = {}
            temp['url'] = a.xpath('./@href')[0]
            temp['title'] = a.xpath('.//div[@class="li-title"]/div/text()')[0]
            temp['year_address'] = ';'.join(a.xpath('.//div[@class="props nowrap"]//text()'))
            temp['tags'] = ';'.join(a.xpath('.//div[@class="prop-tags"]/span/text()'))
            try:
                temp['price'] = a.xpath('.//div[@class="community-price"]/strong/text()')[0]
            except Exception as e:
                temp['price'] = ''
            self.final_res.append(temp)

    def get_neighbor_list(self):
        sql = '''
        with base as (
        select *, row_number() over (partition by url) as sort
        from anjuke_shanghai_city_list)
        select * from base
        where sort =1
        '''
        anjuke_shanghai_city_list = MysqlReader(target='localhost').read_sql(sql=sql, database='gaode')
        anjuke_shanghai_city_list = anjuke_shanghai_city_list.to_dict('records')
        return anjuke_shanghai_city_list

    def parse_detail(self, tree,signle_neighbor):
        detail_info = {}
        for div in tree.xpath('//div[@class="info"]/div[@class="info-list"]/div'):
            temp = {}
            label = div.xpath('./div[@class="label"]/text()')[0]
            try:
                value = div.xpath('./div[@class="hover"]/div[1]/text()')[0].replace('\n', '').replace(' ', '')
            except Exception as e:
                value = ''.join(div.xpath('./div[2]//text()')).replace('\n', '').replace(' ', '')

            temp[label] = value

            signle_neighbor.update(**temp)

        self.final_res.append(signle_neighbor)
        print(signle_neighbor)

    def save_error_url(self, url):
        with open('wrong.txt', 'a+', encoding='utf-8') as fp:
            fp.write(url + ',\n')
        fp.close()

    def data_save(self):
        if self.final_res != []:
            data_df = pd.DataFrame(self.final_res)
            data_df['scrapy_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            MysqlWriter(database_name='gaode', target='localhost').write_df(table_name='anjuke_shanghai_city_list',
                                                                            new_df=data_df,
                                                                            method='append')
            self.final_res = []

    def detail_data_save(self):
        if self.final_res != [] and len(self.final_res)>=25:
            data_df = pd.DataFrame(self.final_res)
            data_df['scrapy_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            MysqlWriter(database_name='gaode', target='localhost').write_df(table_name='anjuke_shanghai_community_detail',
                                                                            new_df=data_df,
                                                                            method='append',type_dict={'detail':JSON})
            self.final_res = []

    def spider(self, url):
        global res, proxies
        try:
            logger.debug('processing ' + url)
            attempts = 0
            success = False
            while attempts < 5 and not success:
                headers['User-Agent'] = random.choice(user_agent)
                proxies = random.choice(self.proxies_list)
                print(proxies)
                if len(self.proxies_list) <= 1:
                    logger.debug('更新代理列表')
                    self.proxies_list = self.get_ip()
                try:
                    res = requests.get(url=url, headers=headers, proxies=proxies, timeout=5)
                    success = True
                except Exception as e:
                    logger.error(e)
                    attempts += 1
                    logger.error('第一次请求失败，正常尝试第{}次请求'.format(attempts))
                    try:
                        self.proxies_list.remove(proxies)
                    except:
                        pass
                    logger.debug('删除无效代理，现长度为{}'.format(len(self.proxies_list)))
                    if attempts == 5:
                        break
            if '系统检测到您正在使用网页抓取工具访问安居客网站' in res.text:
                logger.error('触发反爬')
            tree = etree.HTML(res.text)
            if '正在加载中，请稍后...' in res.text or len(tree.xpath('//div[@class="list-cell"]')) == 0:
                logger.error('没有房子列表，可能ip被ban')
                try:
                    self.proxies_list.remove(proxies)
                except:
                    pass
                logger.debug('删除被ban代理，现长度为{}'.format(len(self.proxies_list)))
                self.save_error_url(url)
                self.spider(url)
            try:
                # self.parse(tree)
                self.parse_detail(tree)
            except Exception as e:
                logger.error('解析失败')
            try:
                next_page = tree.xpath('//a[@class="next next-active"]/@href')[0]
                logger.info('继续爬取下一页 ' + next_page)
                self.spider(next_page)
            except:
                logger.error('下一页按钮无法找到')
            with open('test.html', 'w') as fp:
                fp.write(res.text)
        except Exception as e:
            self.save_error_url(url)
            logger.exception('未知原因，执行错误')

    def detail_spider(self, signle_neighbor):
        global res, proxies
        try:
            logger.debug('processing ' + signle_neighbor['url'])
            attempts = 0
            success = False
            while attempts < 5 and not success:
                headers['User-Agent'] = random.choice(user_agent)
                proxies = random.choice(self.proxies_list)
                if len(self.proxies_list) <= 1:
                    logger.debug('更新代理列表')
                    self.proxies_list = self.get_ip()
                try:
                    res = requests.get(url=signle_neighbor['url'], headers=headers, proxies=proxies, timeout=5, allow_redirects = False)
                    success = True
                except Exception as e:
                    logger.error(e)
                    attempts += 1
                    logger.error('第一次请求失败，正常尝试第{}次请求'.format(attempts))
                    try:
                        self.proxies_list.remove(proxies)
                    except:
                        pass
                    logger.debug('删除无效代理，现长度为{}'.format(len(self.proxies_list)))
                    if attempts == 5:
                        break
            if '系统检测到您正在使用网页抓取工具访问安居客网站' in res.text:
                logger.error('触发反爬')
            tree = etree.HTML(res.text)
            if tree is None:
                self.spider(signle_neighbor['url'])
            if '正在加载中，请稍后...' in res.text :
                logger.error('没有房子列表，可能ip被ban')
                # with open('test1.html', 'w') as fp:
                #     fp.write(res.text)
                try:
                    self.proxies_list.remove(proxies)
                except:
                    pass
                logger.debug('删除被ban代理，现长度为{}'.format(len(self.proxies_list)))
                # self.spider(signle_neighbor['url'])
            # if  tree.xpath('//div[@class="info"]/div[@class="info-list"]/div') == []:
            #     self.spider(signle_neighbor['url'])
            try:
                self.parse_detail(tree, signle_neighbor)
            except Exception as e:
                logger.error('解析失败')

        except Exception as e:
            logger.exception('未知原因，执行错误')

    def run_spider(self):
        neighbor_list = self.get_neighbor_list()

        self.proxies_list = self.ip_pool(ip_url)
        for mark, single_neighbor in enumerate(neighbor_list):
            if len(self.proxies_list) < 3:
                time.sleep(4)
                self.proxies_list = self.ip_pool(ip_url)

            if mark >= 500:
                logger.critical('正在抓取列表的第{}个url'.format(mark))
                self.detail_spider(single_neighbor)
                logger.info('结果长度为{}'.format(len(self.final_res)))
            self.detail_data_save()


if __name__ == '__main__':
    CrawlSpider().run_spider()
