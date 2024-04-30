import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st

import tiktoken
from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
import time




def num_tokens_from_prompt(tweets_list: [], encoding_name: str,prompt:str) -> int:
    total_token_num = 0
    for tweets in tweets_list:
        # 计算每个作者的推文token数量
        prompt = f"""{prompt}
            {{ 
    
            {tweets} 
    
            }}
            """

        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(prompt))
        total_token_num += num_tokens
    return total_token_num


# 自定义等待策略函数
def wait_custom_exponential(min_wait, max_wait, factor):
    def wait_func(retry_state):
        # 计算等待时间，使用指数退避加上递增因子
        return random.uniform(min_wait, max_wait) + factor * retry_state.attempt_number

    return wait_func


@retry(wait=wait_custom_exponential(min_wait=10, max_wait=20, factor=5), stop=stop_after_attempt(3))
def summarize_every_kol_tweets(tweets: str,custom_prompt:str,chat):
    # 计算每个作者的推文token数量
    prompt = f"""{custom_prompt}
{{ 
{tweets} 
}}
"""

    messages = [

        HumanMessage(
            content=prompt

        ),
    ]
    #
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(prompt))

    result = chat(messages).content

    if 'N.A.' not in result:
        return num_tokens, result
    else:
        return num_tokens, None


def summarize_tweet_text(tweets_text:str,prompt:str,chat):
    # 创建锁对象
    lock = threading.Lock()
    total_tweet_content=''
    # Split the string into individual tweets
    individual_tweets = tweets_text.strip().split('-------\n')

    # Initialize an empty dictionary to store tweets grouped by author
    tweets_by_author = {}

    # Iterate through each tweet and group by author
    for tweet in individual_tweets:
        tweet_lines = tweet.strip().split('\n')
        author = tweet_lines[0]
        if author not in tweets_by_author:
            tweets_by_author[author] = []
        tweets_by_author[author].append(tweet+'-------')

    # Initialize an empty list to store grouped tweets content
    grouped_tweets_list = []

    # Iterate through grouped tweets and concatenate their content
    for author, tweets in tweets_by_author.items():
        grouped_tweets_list.append('\n'.join(tweets))
    
    requests = grouped_tweets_list.__iter__()
    tweets_list = []
    while True:
        try:
            tweets = next(requests)
        except StopIteration:
            if tweets_list and len(tweets_list)>0:
                total_token = num_tokens_from_prompt(tweets_list, "cl100k_base",prompt)
                if total_token and total_token > 0:
                    futures = []
                    # 多线程处理
                    with ThreadPoolExecutor(max_workers=len(tweets_list)) as executor:
                        for tw in tweets_list:
                            future = executor.submit(summarize_every_kol_tweets, tw,prompt,chat)
                            futures.append(future)
                        start_time = time.time()
                        for fu in as_completed(futures):
                            result = fu.result()[1]
                            if result:
                                # 获取锁
                                lock.acquire()
                                
                                try:
                                    
                                    total_tweet_content +=(result+"\n------------------------\n")
                                    # 修改共享变量
                                finally:
                                    # 释放锁
                                    lock.release()

                        end_time = time.time()
                        time_diff_seconds = end_time - start_time

                        print('执行时间间隔=', time_diff_seconds)

                        tweets_list.clear()
                        # tweets_list.append(tweets)
            print('已经到底了2')
            break
        if not tweets:
            print('已经到底了3')
            break
        tweets_list.insert(0, tweets)
        total_token = num_tokens_from_prompt(tweets_list, "cl100k_base",prompt)
        if total_token > 20000:
            tweets_list.remove(tweets)

            futures = []
            # 多线程处理
            with ThreadPoolExecutor(max_workers=len(tweets_list)) as executor:
                for tw in tweets_list:
                    future = executor.submit(summarize_every_kol_tweets, tw,prompt,chat)
                    futures.append(future)
                start_time = time.time()
                for fu in as_completed(futures):
                    result = fu.result()[1]
                    if result:
                        # 获取锁
                        lock.acquire()
                        
                        try:
                            
                            total_tweet_content +=(result+"\n------------------------\n")
                            # 修改共享变量
                        finally:
                            # 释放锁
                            lock.release()
                end_time = time.time()
                time_diff_seconds = end_time - start_time

                print('执行时间间隔=', time_diff_seconds)

                tweets_list.clear()
                tweets_list.append(tweets)
                time.sleep(int(st.secrets["timeout"]))
    return total_tweet_content
