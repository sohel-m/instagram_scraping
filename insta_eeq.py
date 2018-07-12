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
import shutil
import pickle
from fake_useragent import UserAgent
from multiprocessing import Pool


################################################################################
################################################################################
class App:

    # INCLUDE DIFFERENT CATEGORIES ON INSTAGRAM TO DERIVE FOLLOWERS FROM
    def __init__(self, username='', password='',targetlist=['leomessi','iamsrk','jenselter','lelepons','chrisburkard','wildlifeplanet','5.min.crafts','narendramodi']):

        self.username = username
        self.password = password
        self.targetlist = targetlist
        self.main_url = "https://www.instagram.com/"
        self.error = False
        self.profiles=set()
        self.driver = webdriver.Chrome()
        #self.driver = webdriver.Chrome(chrome_options=options) #to open with new options
        self.log_in()
        if self.error == False:
            self.get_all_following()
        self.driver.close()

        ########################################################################

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

            ####################################################################

    def close_pop_tabs(self):
        try:
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception as e:
            pass

            ####################################################################

    def get_all_following(self):

        for target in self.targetlist:

            self.driver.get(self.main_url + target)

            sleep(5)

            following_tag = self.driver.find_element_by_xpath('//a[text()=" followers"]')
            following_value = self.driver.find_element_by_xpath('//a[text()=" followers"]/span')
            following_value = int(following_value.get_attribute('title').replace(',',''))
            print('Followers=',following_value)
            following_tag.click()
            sleep(5)
            #scrolls = int(following_value//12) + 3
            scrolls = 100 # to gather about 1200 usernames half of which may be private
            try:
                for value in range(scrolls):
                    print('Scroll:',value)
                    a = self.driver.find_element_by_xpath('//a[@class="FPmhX notranslate zsYNt "]')
                    a.send_keys(Keys.END)
                    self.driver.implicitly_wait(3)
                    sleep(1)
                    a.send_keys(Keys.PAGE_UP)
                    sleep(1)

            except Exception as e:
                self.error = True
                print(e)
                print('Some error occurred while trying to scroll down')

            alist = self.driver.find_elements_by_xpath('//a[@class="FPmhX notranslate zsYNt "]')
            for a in alist:
                self.profiles.add(a.get_attribute('href'))

            print("Total no. of profiles = ", len(self.profiles))

################################################################################
################################################################################
class InstagramScraper:

    def __init__(self, user_agents=None, proxy=None):
        self.user_agents = user_agents
        self.proxy = 'https://USER:PASS@'
        self.error = False
        ############################################################

    def __request_url(self, url):

        try:
            response = requests.get(url, timeout= 15, headers={'User-Agent': ua.random}, proxies={'http': self.proxy,'https': self.proxy})
            response.raise_for_status()
        except requests.HTTPError:
            print('Received non 200 status code from Instagram for>>',url)
            self.error = True
        except requests.RequestException:
            raise requests.RequestException
        else:
            return response.text

        ####################################################################

    @staticmethod
    def extract_json_data(html):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('body')
        script_tag = body.find('script')
        raw_string = script_tag.text.strip().replace('window._sharedData =', '').replace(';', '')
        return json.loads(raw_string)

        ####################################################################

    def profile_page_metrics(self, profile_url):
        results = {}
        need_keys=['biography','connected_fb_page','edge_follow','edge_followed_by','edge_owner_to_timeline_media','edge_media_collections','external_url','has_channel','highlight_reel_count','is_verified','username','profile_pic_url','full_name','is_private']
        try:
            response = self.__request_url(profile_url)
            if self.error == True:
                return None
            json_data = self.extract_json_data(response)
            metrics = json_data['entry_data']['ProfilePage'][0]['graphql']['user']
        except Exception as e:
            raise e
        else:
            if metrics['is_private']==True:
                self.error = True
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

        ####################################################################

    def profile_page_recent_posts(self, profile_url):
        results = []
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

        ####################################################################

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

        return results

################################################################################
################################################################################

def initialize_workbook(bookname):

    global row_no,workbook,worksheet
    row_no = 2

    print('writing to excel')
    workbook = Workbook(bookname)
    worksheet = workbook.add_worksheet()

    worksheet.write('A1', 'Instagram ID')
    worksheet.write('B1', 'Name')
    worksheet.write('C1', 'Bio')
    worksheet.write('D1', 'No. of posts')
    worksheet.write('E1', 'Following')
    worksheet.write('F1', 'Followers')
    worksheet.write('G1', 'Image')
    worksheet.write('H1', 'FB Page')
    worksheet.write('I1', 'Highlight Reel')
    worksheet.write('J1', 'Verified')
    worksheet.write('K1','Media Collections')

    worksheet.write('L1','Post 1 Info')
    worksheet.write('M1','Post 2 Info')
    worksheet.write('N1','Post 3 Info')
    worksheet.write('O1','Post 4 Info')
    worksheet.write('P1','Post 5 Info')
    worksheet.write('Q1','Post 6 Info')
    worksheet.write('R1','Post 7 Info')
    worksheet.write('S1','Post 8 Info')
    worksheet.write('T1','Post 9 Info')
    worksheet.write('U1','Post 10 Info')
    worksheet.write('V1','Posts 11 Info')
    worksheet.write('W1','Posts 12 Info')

def write2excel(record):

    global row_no,worksheet

    for i in range(12-len(record['posts_info'])):
        record['posts_info'].append(None)

    worksheet.write('A'+str(row_no), record['profile_info']['username'])
    worksheet.write('B'+str(row_no), record['profile_info']['full_name'])
    worksheet.write('C'+str(row_no), record['profile_info']['biography'])
    worksheet.write('D'+str(row_no), record['profile_info']['edge_posts'])
    worksheet.write('E'+str(row_no), record['profile_info']['edge_follow'])
    worksheet.write('F'+str(row_no), record['profile_info']['edge_followed_by'])
    worksheet.write('H'+str(row_no), record['profile_info']['connected_fb_page'])
    worksheet.write('I'+str(row_no), record['profile_info']['highlight_reel_count'])
    worksheet.write('J'+str(row_no), record['profile_info']['is_verified'])
    worksheet.write('K'+str(row_no), record['profile_info']['edge_media_collections'])

    worksheet.write('L'+str(row_no), str(record['posts_info'][0]))
    worksheet.write('M'+str(row_no), str(record['posts_info'][1]))
    worksheet.write('N'+str(row_no), str(record['posts_info'][2]))
    worksheet.write('O'+str(row_no), str(record['posts_info'][3]))
    worksheet.write('P'+str(row_no), str(record['posts_info'][4]))
    worksheet.write('Q'+str(row_no), str(record['posts_info'][5]))
    worksheet.write('R'+str(row_no), str(record['posts_info'][6]))
    worksheet.write('S'+str(row_no), str(record['posts_info'][7]))
    worksheet.write('T'+str(row_no), str(record['posts_info'][8]))
    worksheet.write('U'+str(row_no), str(record['posts_info'][9]))
    worksheet.write('V'+str(row_no), str(record['posts_info'][10]))
    worksheet.write('W'+str(row_no), str(record['posts_info'][11]))

    filename = record['profile_info']['username'] +'.jpg'
    image_path = os.path.join('Profile_Images', filename)
    r = requests.get(record['profile_info']['profile_pic_url'],stream='True')
    with open(image_path, 'wb') as file:
        shutil.copyfileobj(r.raw, file)  # source -  destination

    worksheet.insert_image('G'+str(row_no), image_path)

################################################################################
################################################################################

if __name__ == '__main__':

    ua=UserAgent()
    total_request=0
    all_profiles=[]

# COLLECTING USERNAMES AND STORING IN A FILE
    '''app = App()
    all_profiles = list(app.profiles)
    print(len(all_profiles))
    pprint(all_profiles)
    with open('all_profiles', 'wb') as fp:
        pickle.dump(all_profiles, fp)'''

# LOADING USERNAMES FROM FILE
    with open('all_profiles', 'rb') as fp:
        all_profiles=pickle.load(fp)

    print (len(all_profiles))

# INITAILIZING WORKBOOK
    initialize_workbook('all_profile_details.xlsx')

# EXTRACT USER INFORMATION AND SAVING TO WORKBOOK
    try:
        for profile in all_profiles:
            record ={'profile_info':{},'posts_info':[]}
            k = InstagramScraper()
            profile_info = k.profile_page_metrics(profile)
            if k.error==True:
                print('Continuing with next account')
                continue
            total_request+=1
            print('requestno:',total_request)


            record['profile_info'] = profile_info

            if profile_info['edge_posts'] > 0:
                results = k.profile_page_recent_posts(profile)
                with Pool(processes=6) as p:
                    posts_info=p.map(k.post_info, results) ## MULTIPROCESSING BLOCK
                    sleep(0.5)
                    total_request+=len(results)
                    print('requestno:',total_request)
                    '''if total_request >=250:
                        sleep(3)
                        total_request=0'''
            else:
                posts_info = [None,None,None,None,None,None,None,None,None,None,None,None]


            record['posts_info'] = posts_info
            write2excel(record)
            row_no += 1

        print('Completed')
        workbook.close()

    except:
        workbook.close()
        raise
