import json
import requests
from bs4 import BeautifulSoup
from pprint import pprint
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from time import sleep
from xlsxwriter import Workbook
import os

from fake_useragent import UserAgent
ua=UserAgent()
total_request=0
################################################################################
class App:

    def __init__(self, username='', password='', target='leomessi'): #Change this to your Instagram details
        self.username = username
        self.password = password
        self.target = target
        self.main_url = "https://www.instagram.com/"
        self.error = False
        self.profiles={}
        self.driver = webdriver.Chrome()
        #self.driver = webdriver.Chrome(chrome_options=options) #to open with new options
        self.log_in()
        if self.error == False:
            self.get_all_following()
        self.driver.close()

    def log_in(self):
        try:
            self.driver.get('https://www.instagram.com/accounts/login/')
            sleep(3)
            user_name_input = self.driver.find_element_by_xpath('//input[@aria-label="Phone number, username, or email"]')
            user_name_input.send_keys(self.username)
            sleep(1)
            password_input = self.driver.find_element_by_xpath('//input[@aria-label="Password"]')
            password_input.send_keys(self.password)
            sleep(1)
            user_name_input.submit()
            sleep(3)
            self.close_pop_tabs()

        except Exception as e:
            print(e)
            print('Some exception occurred while trying to find username or password field')
            self.error = True

        self.driver.get(self.main_url + self.target)
        sleep(1)

################################################################################
    def close_pop_tabs(self):
        try:
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception as e:
            pass

################################################################################


    def get_all_following(self):

        following_tag = self.driver.find_element_by_xpath('//a[text()=" followers"]')
        following_value = self.driver.find_element_by_xpath('//a[text()=" followers"]/span')
        following_value = int(following_value.get_attribute('title').replace(',',''))
        print('Followers=',following_value)
        following_tag.click()
        sleep(3)
        #scrolls = int(following_value//12) + 3
        scrolls = 100 # to gather about 1200 usernames half of which may be private 
        try:
            for value in range(scrolls):
                print(value)
                alist=self.driver.find_elements_by_xpath('//a[@class="FPmhX notranslate zsYNt "]')
                for a in alist:
                    href = a.get_attribute('href')
                    self.profiles[href] = a.text

                sleep(1)
                a.send_keys(Keys.END)

        except Exception as e:
            self.error = True
            print(e)
            print('Some error occurred while trying to scroll down')

        print("Total no. of profiles = ", len(self.profiles))

################################################################################
################################################################################
class InstagramScraper:

    def __init__(self, user_agents=None, proxy=None):
        self.user_agents = user_agents
        self.proxy = proxy
        self.error = False

    def __request_url(self, url):
        try:
            response = requests.get(url, headers={'User-Agent': ua.random}, proxies={'http': self.proxy,'https': self.proxy})
            total_request+=1
            print('requestno:',total_request)
            response.raise_for_status()
        except requests.HTTPError:
            raise requests.HTTPError('Received non 200 status code from Instagram')
        except requests.RequestException:
            raise requests.RequestException
        else:
            return response.text

    @staticmethod
    def extract_json_data(html):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('body')
        script_tag = body.find('script')
        raw_string = script_tag.text.strip().replace('window._sharedData =', '').replace(';', '')
        return json.loads(raw_string)

    def profile_page_metrics(self, profile_url):
        results = {}
        need_keys=['biography','connected_fb_page','edge_follow','edge_followed_by','edge_owner_to_timeline_media','edge_media_collections','external_url','has_channel','highlight_reel_count','is_verified','username','profile_pic_url','full_name','is_private']
        try:
            response = self.__request_url(profile_url)
            json_data = self.extract_json_data(response)
            metrics = json_data['entry_data']['ProfilePage'][0]['graphql']['user']
        except Exception as e:
            raise e
        else:
            if metrics['is_private']==True:
                print(profile_url,'is a private account')
                return results
            for key, value in metrics.items():
                if key in need_keys:
                    if isinstance(value, dict):
                        value = value['count']
                        results[key] = value
                    else:
                        results[key] = value

        results[u'edge_posts']=results.pop('edge_owner_to_timeline_media',None)
        return results

    def profile_page_recent_posts(self, profile_url):
        results = []
        if self.error==True:
            print('Private account')
        try:
            response = self.__request_url(profile_url)
            json_data = self.extract_json_data(response)
            metrics = json_data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']["edges"]
        except Exception as e:
            raise e
        else:
            for node in metrics:
                node = node.get('node')
                if node and isinstance(node, dict):
                    results.append('https://www.instagram.com/p/'+node['shortcode'])
        return results


    def post_info(self,post_url):
        need_keys=["__typename","location","is_ad","caption_is_edited","taken_at_timestamp","display_url","comments_disabled"]
        dimensions,caption,likes_count,comments_count,all_comments=(0,0),'',0,0,{}

        results={}
        try:
            response = self.__request_url(post_url)
            json_data = self.extract_json_data(response)
            metrics = json_data['entry_data']['PostPage'][0]['graphql']['shortcode_media']
        except Exception as e:
            raise e

        else:
            for node,value in metrics.items():

                if node in need_keys:
                    results[node]=value

                elif (node=='dimensions'):
                    dimensions=(value['width'],value['height'])

                elif(node=='edge_media_preview_like'):
                    likes_count = value['count']

                elif (node=='edge_media_to_comment')and(metrics['comments_disabled']==False):
                    comments_count = value['count']
                    for i in value['edges']:
                        all_comments[i['node']['owner']['username']] = i['node']['text']

                elif(node=='edge_media_to_caption')and(value['edges']!=[]):
                    caption = value['edges'][0]['node']['text']


        results['all_comments']=all_comments
        results['dimensions']=dimensions
        results['likes_count']=likes_count
        results['caption']=caption
        results['comments_count']=comments_count

        #pprint(results)


if __name__ == '__main__':
    app = App()
    all_profiles = list(app.profiles.keys())
    #print (all_profiles)

    k = InstagramScraper()

    '''for profile in all_profiles:
        results = k.profile_page_metrics(profile)
        pprint(results)
        results = k.profile_page_recent_posts(profile)
        for post in results:
            k.post_info(post)'''
# server blocks after request 490 under 4 min
