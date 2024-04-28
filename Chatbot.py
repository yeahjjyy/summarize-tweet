
import os
import uuid
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
import streamlit as st
import tiktoken
from langchain_community.callbacks import get_openai_callback
from sqlalchemy import  create_engine,Table, Column, MetaData, Integer, String, JSON, Text,text
from sqlalchemy.sql import select
from sqlalchemy.dialects.postgresql import ARRAY
import datetime
from datetime import timedelta
from streamlit_tags import st_tags, st_tags_sidebar

from param_summarize_tweet import summarize_tweet_text

os.environ["LANGCHAIN_TRACING_V2"] = 'true'
os.environ["LANGCHAIN_ENDPOINT"] = 'https://api.smith.langchain.com'
os.environ["LANGCHAIN_PROJECT"] = st.secrets["LANGCHAIN_PROJECT"]
os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]

hide_st_style="""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
<![]()yle>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

    
@st.cache_resource
def get_engine():
    engine = create_engine(
        st.secrets["url"]
    )
    return engine

# @st.cache_data(ttl=60)
def get_twitter(project_name_list):
    engine = get_engine()

    # 查询所有的twitter博主
    twitter_list = []
    metadata = MetaData()
    twitter_base_content = Table('twitter_base_content', metadata,
                                    Column('id', Integer, primary_key=True),
                                    Column('tweet_id', String),
                                    Column('influencer_id', String),
                                    Column('original_text', JSON),
                                    Column('publish_time', String)
                                )
    twitter_base_influencers = Table('twitter_base_influencers', metadata,
                                    Column('id', Integer, primary_key=True),
                                    Column('twitter_username', String),
                                    Column('influencer_id', String),
                                    Column('project_name', String),
                                    Column('project_name_array', ARRAY(Text))
                                )
    query_project_twitter = select(twitter_base_influencers.c.twitter_username).where(twitter_base_influencers.c.project_name_array.op('&&')(project_name_list))
    with engine.connect() as conn:
        if project_name_list and 'all' in project_name_list:
            # query_twitter = select(twitter_base_content.c.influencer_id).group_by(twitter_base_content.c.influencer_id)
            project_name_list = ['daliy_twitter']
            query_project_twitter = select(twitter_base_influencers.c.twitter_username).where(twitter_base_influencers.c.project_name_array.op('&&')(project_name_list))

            result = conn.execute(query_project_twitter)
            for row in result:
                twitter_list.append(row[0])
        else:
            result = conn.execute(query_project_twitter)
            project_twitter_list = []
            for row in result:
                project_twitter_list.append(row[0])
            query_twitter = select(twitter_base_content.c.influencer_id).group_by(twitter_base_content.c.influencer_id).having(twitter_base_content.c.influencer_id.in_(project_twitter_list))
            result = conn.execute(query_twitter)
            for row in result:
                twitter_list.append(row[0])
    if twitter_list:
        twitter_list.insert(0,'all')
        st.session_state['selection_output'] = twitter_list
    else:
        st.session_state['selection_output'] = ['no data']
    return twitter_list


def get_all_twitter():
    # st.write("You selected:", st.session_state.selected_projects )
    
    if not st.session_state.selected_projects:
        st.session_state['selection_output'] = []
    
    return get_twitter(st.session_state.selected_projects)


with st.sidebar:

    selected_option = st.selectbox('请选择一个公司', ['anthropic', 'openai'])
    if selected_option == 'anthropic':
        model_selected_option = st.selectbox('请选择一个模型', ['claude-3-opus-20240229', 'claude-3-sonnet-20240229','claude-3-haiku-20240307'])
    else:
        model_selected_option = st.selectbox('请选择一个模型', ['gpt-4-0125-preview', 'gpt-4-turbo','gpt-3.5-turbo-0125'])
    custom_openai_api_key = st.text_input("API Key", key="chatbot_api_key", type="password")

    if 'selected_projects' not in st.session_state:
        st.session_state['selected_projects'] = []

    project_options = st.multiselect(
    'Please select one or more project',
    ['daliy_twitter'],
    default=['daliy_twitter'],
    key='selected_projects',
    on_change=get_all_twitter
    )

    # 设置日期范围的初始值
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=2)

    # 使用st.date_input获取日期范围
    date_range = st.date_input("Select a date range:", [start_date, end_date])

    # st.write("Start date:", date_range[0])
    # st.write("End date:", date_range[1])

    # 获取当前时间
    current_time = datetime.datetime.now().time()
    col1, col2 = st.columns(2)

    # 使用两个st.time_input获取时间范围
    with col1:
        start_time = st.time_input('Select start time:', value=None)
    with col2:
        end_time = st.time_input('Select end time:', value=None)

    # st.write("Start time:", start_time)
    if not start_time:
        start_time = datetime.datetime.now().time()
    if not end_time:
        end_time = datetime.datetime.now().time()
    if len(date_range)>0:
        start_datetime = datetime.datetime.combine(date_range[0], start_time)
        start_formatted_date = start_datetime.strftime('%Y-%m-%d %H:%M:%S')
    if len(date_range)>1:
        end_datetime = datetime.datetime.combine(date_range[1], end_time)
        end_formatted_date = end_datetime.strftime('%Y-%m-%d %H:%M:%S')



    if 'selection_output' not in st.session_state:
        st.session_state['selection_output'] = []
    if  st.session_state.selection_output:
        options = st.multiselect(
        'Please select one or more twitter',
        st.session_state.selection_output,
        )

    key_words = st_tags_sidebar(
        label='Enter Keywords tag:',
        text='Press enter to add tweet keywords tag',
        suggestions=['btc'],
        maxtags = 5
    )
    content_length_limit = st.number_input("Enter length", min_value=0, max_value=10000, step=1,help='The minimum length of tweet content. Only tweets exceeding this length will be returned.')

    show_fields = st.multiselect(
    'Please select one or more fields',
    ['author','timestamp','source link','tweet content'],
    )

if custom_openai_api_key:
    if selected_option=='anthropic':
        chat = ChatAnthropic(
            anthropic_api_key=custom_openai_api_key,model_name=model_selected_option)
    else:
        chat = ChatOpenAI(openai_api_key=custom_openai_api_key, model_name=model_selected_option)
        

def contains_any_efficient(string, char_list):
    """检查字符串是否包含列表中的任一字符或子字符串"""
    for item in char_list:
        if item in string:
            return True
    return False

def all_elements_in_another(list1, list2):
    """检查 list1 的所有元素是否都在 list2 中"""
    return set(list2).issubset(set(list1))

def get_return_tweet(select_return_fields,row):
    if not select_return_fields:
        return f'''author: {row[1]} 
timestamp: {row[3]} 
source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    if all_elements_in_another(select_return_fields, ['author','timestamp']) or all_elements_in_another(select_return_fields, ['author','timestamp','tweet content']):
        return f'''author: {row[1]} 
timestamp: {row[3]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['author','source link','tweet content']):
        return f'''author: {row[1]} 
source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['timestamp','source link','tweet content']) or all_elements_in_another(select_return_fields, ['timestamp','source link']):
        return f'''timestamp: {row[3]} 
source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['author','source link']):
        return f'''author: {row[1]} 
source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['author','tweet content']):
        return f'''author: {row[1]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['tweet content']):
        return f'''tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['author']):
        return f'''author: {row[1]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['source link']):
        return f'''source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    elif all_elements_in_another(select_return_fields, ['timestamp']):
        return f'''timestamp: {row[3]} 
tweet content: {row[2]} {row[4]} 
-------
'''
    else:
        return f'''author: {row[1]} 
timestamp: {row[3]} 
source link: {row[0]} 
tweet content: {row[2]} {row[4]} 
-------
'''



def get_tweet_by_time():
    total_text = ''
    engine = get_engine()

    # 查询所有的twitter博主
    with engine.connect() as conn:
        if 'all' in options:
            influencer_ids = ", ".join(f"'{elem}'" for elem in st.session_state.selection_output)
            sql = text(f"select tweet_id, influencer_id,original_text ->> 'text' as tweet_content, publish_time, original_text -> 'quote' ->> 'text' as quote_text from twitter_base_content  where influencer_id in ({influencer_ids}) and publish_time_ts BETWEEN '{str(start_formatted_date)}' AND '{str(end_formatted_date)}'")
        else:
            influencer_ids = ", ".join(f"'{elem}'" for elem in options)
            sql = text(f"select tweet_id, influencer_id,original_text ->> 'text' as tweet_content, publish_time, original_text -> 'quote' ->> 'text' as quote_text from twitter_base_content  where influencer_id in ({influencer_ids}) and publish_time_ts BETWEEN '{str(start_formatted_date)}' AND '{str(end_formatted_date)}'")
        result = conn.execute(sql)
        for row in result:
            # 判断长度
            if len(str({row[2]})+str({row[4]})) < content_length_limit and content_length_limit > 0:
                continue
            # 判断是否包含某个字符
            if key_words and not contains_any_efficient((str({row[2]})+str({row[4]})),key_words):
                continue
            tweet = get_return_tweet(show_fields,row)
#             tweet = f'''author: {row[1]} 
# timestamp: {row[3]} 
# source link: {row[0]} 
# tweet content: {row[2]} {row[4]} 
# -------
# '''
            total_text+=tweet
    return total_text



def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens
def truncate_string(input_string):
    # 检查字符串长度
    if len(input_string) > 50000:
        # 如果超过10000，则截取前10000个字符并加上...
        return input_string[:20000] + '...'
    else:
        # 如果没有超过，返回原字符串
        return input_string
    
st.title("💬 generate prompt")
display_container0 = st.empty()
display_container = st.empty()
display_container2 = st.empty()
display_container3 = st.empty()
if 'last_content' not in st.session_state:
    st.session_state['last_content'] = ''
if 'kol_tweet_output' not in st.session_state:
    st.session_state['kol_tweet_output'] = ''
if st.session_state.last_content:
    token_num = num_tokens_from_string(st.session_state.last_content, "cl100k_base")
    export_file_name = str(uuid.uuid4())+"_twitter.txt"
    export_file_name2 = str(uuid.uuid4())+"_twitter.txt"
    with display_container0:
        col13, col12 = st.columns(2)
        with col13:
            st.markdown(''':rainbow[tweet content]''')
        with col12:
            st.markdown(''':rainbow[tweet summrize result]''')

    with display_container:
        col6, col7 = st.columns(2)
        with col6:
            with st.container(height=500):
                st.code(truncate_string(st.session_state.last_content))
        with col7:
            with st.container(height=500):
                st.code(st.session_state.kol_tweet_output)
    with display_container2:
        col3, col4 = st.columns(2)
        with col3:
            st.download_button(
                label="export",
                data=st.session_state.last_content,
                file_name=export_file_name,
                mime="text/plain"
            )
        with col4:
            st.download_button(
                label="export",
                data=st.session_state.kol_tweet_output,
                file_name=export_file_name2,
                mime="text/plain"
            )
    with display_container3:
        st.write('token length = '+ str(token_num))

prompt = st.chat_input("please input prompt")

if prompt:
    if not project_options:
        st.info("please select project.")
        st.stop()
    if not options:
        st.info("please select twitter.")
        st.stop()
    if not custom_openai_api_key :
        st.info("Please add your OpenAI API key ")
        st.stop()
    delta = abs(end_datetime - start_datetime)
    
    if delta <= timedelta(days=3) :
        
        with st.spinner("processing..."):
            data = get_tweet_by_time()
            total_result = summarize_tweet_text(data,prompt,chat)
            if total_result:
                st.session_state['kol_tweet_output'] = total_result

            content = 'no data'
            # 根据twitter 和 日期查询推文
            # with st.container(height=500):
            if data:
                content = data
                # st.session_state['last_content'] = ''
                display_container.empty()
            st.session_state['last_content'] = content
            token_num = num_tokens_from_string(content, "cl100k_base")
            export_file_name = str(uuid.uuid4())+"_twitter.txt"
            export_file_name2 = str(uuid.uuid4())+"_twitter.txt"
            # display_container.empty()
            with display_container0:
                col15, col16 = st.columns(2)
                with col15:
                    st.markdown(''':rainbow[tweet content]''')
                with col16:
                    st.markdown(''':rainbow[kol tweet summrize result]''')

            
            with display_container:
                col8, col9 = st.columns(2)
                with col8:
                    with st.container(height=500):
                        st.code(truncate_string(content))
                with col9:
                    with st.container(height=500):
                        st.code(total_result)

            with display_container2:
                col10, col11 = st.columns(2)
                with col10:
                    if content:
                        st.download_button(
                            label="export",
                            data=content,
                            file_name=export_file_name,
                            mime="text/plain"
                        )
                with col11:
                    if content:
                        st.download_button(
                            label="export",
                            data=total_result,
                            file_name=export_file_name2,
                            mime="text/plain"
                        )                
            with display_container3:
                st.write('token length = '+ str(token_num))

    else :
        st.info("The date interval is more than 3 days.")
        st.stop()
