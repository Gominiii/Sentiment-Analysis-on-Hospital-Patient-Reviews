import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import re
import pandas as pd
import json

def getHospitalInfo(entity_info):
    res = {
        'Name': entity_info.get('name'),
        'Type': entity_info.get('multispeciality_text'),
        'Locality': entity_info.get('locality'),
        'Min_price': entity_info.get('min_price'),
        'Max_price': entity_info.get('max_price'),  # Assuming you meant 'max_price' instead of repeating 'min_price'
        'Doctors': entity_info.get('doctors_count'),
        'Specialities': int(entity_info.get('speciality_text')[:len(entity_info.get('speciality_text'))-len('Specialities')]),
        'reviews_count': entity_info.get('reviews_count'),
        'Work time': entity_info.get('practice_timings'),
        'profile_url': entity_info.get('profile_url'),
        'Score':0
    }

    return res

def getFeedbackUrl(org_str, i):
    extracted_string = None

    # Updated pattern to match and extract the hospital names
    pattern = r"/[^/]+/hospital/([^?]+)"


    match = re.search(pattern, org_str)
    if match:
        # Extract the substring that matches the pattern
        extracted_string = match.group(1)
    res = "https://www.practo.com/marketplace-api/dweb/profile/establishment/feedback?slug=" + extracted_string + "&profile_type=ESTABLISHMENT&page=" + str(i) + "&mr=true&active_filter%5Bid%5D=0&active_filter%5Btext%5D=All&active_filter%5Btype%5D=All&show_recommended_reviews=true&show_feedback_summary_tags=true"
    return res

cityArray = ['Bangalore', 'Mysore', 'Mangalore', 'Hubli', 'Mumbai', 'Delhi', 'Chennai', 'Hyderabad', 'Kolkata', 'Ahmedabad']
org_url = 'https://www.practo.com/search/hospitals?results_type=hospital&q=%5B%7B%22word%22%3A%22hospital%22%2C%22autocompleted%22%3Atrue%2C%22category%22%3A%22type%22%7D%5D&city='
nltk.download('vader_lexicon')
sia = SentimentIntensityAnalyzer()

allData = []
for cityname in cityArray:
    # Define the base URL for constructing absolute URLs
    base_url = org_url + cityname
    getMoreList_url = 'https://www.practo.com/marketplace-api/dweb/listing/hospital/v2?search_source=new&ad_limit=2&topaz=true&with_ad=true&platform=desktop_web&with_seo_data=true&placement=DOCTOR_SEARCH&city='+cityname+'&q=%5B%7B%22word%22%3A%22hospital%22%2C%22autocompleted%22%3Atrue%2C%22category%22%3A%22type%22%7D%5D&results_type=hospital&page='
    # Send a GET request to the main page to extract initial URLs
    response = requests.get(base_url, timeout=100)

    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all script tags
        script_tags = soup.find_all('script')

        first_json_data = None
        for script in script_tags:
            if script.string and 'window.__' in script.string:
                # Use regex to extract JSON data from window.__...__ = {...}
                match = re.search(r'window\.__.*?__\s*=\s*(\{.*?\})', script.string, re.DOTALL)
                if match:
                    json_str = match.string  # Extract JSON string
                    json_str = json_str[match.regs[1][0]:]
                    first_json_data = json.loads(json_str)  # Parse JSON string to a dictionary
                    if "hospitallistin" in first_json_data:
                        break

        # Load the extracted JSON string into a Python dictionary
        if first_json_data:
            List10 = first_json_data["establishments"]["hospitalListing"]["hospitals"]["entities"]
            for entity_id, entity_info in List10.items():
                HInfo = getHospitalInfo(entity_info)
                if(HInfo['reviews_count'] != '' and HInfo['reviews_count'] > 20):
                    allData.append(HInfo)

        n = 2
        f = 3
        getCnt = 10
        while f:
            getMoreList_url += str(n)
            res = requests.get(getMoreList_url, timeout=100)
            json_data = res.json()
            if 'establishments' in json_data:
                addedList10 = json_data['establishments']['entities']
                getCnt = len(json_data['establishments']['entities'])
                for entity_id, entity_info in addedList10.items():
                    HInfo = getHospitalInfo(entity_info)
                    if(HInfo['reviews_count'] != '' and HInfo['reviews_count'] > 20):
                        allData.append(HInfo)
            else:
                f -= 1
    else:
        print(f"Failed to retrieve content from {base_url} with status code: {response.status_code}")

for data in allData:
    q = 0
    cnt = 0
    patient_sentiment = {
        'neg': 0,
        'neu': 0,
        'pos': 0,
        'compound': 0
    }
    while q < 2:
        q += 1
        feedback_url = getFeedbackUrl(data['profile_url'], q)
        feedback_response = requests.get(feedback_url, timeout=10)
        if feedback_response.status_code == 200:
            feedback_json = feedback_response.json()
            for i in range(10):
                profileFeedback = feedback_json["data"]["profileFeedback"]
                if profileFeedback:
                    review = profileFeedback["reviews"][i]["review"]
                    if review:
                        cnt += 1
                        review_text = review["survey_response"]["review_text"]
                        sentiment = sia.polarity_scores(review_text)
                        for key, value in patient_sentiment.items():
                            patient_sentiment[key] += sentiment[key]
    if cnt:
        for key, value in patient_sentiment.items():
            patient_sentiment[key] /= cnt
    data['Score'] = patient_sentiment['compound']
    print(data['Name'] + ' : ' + data['Score'])


    
    
# Sort the array by 'score' in descending order
sorted_allData = sorted(allData, key=lambda x: x['Score'], reverse=True)

# Add an 'index' to each dictionary
for i, item in enumerate(sorted_allData):
    item['Rank'] = i + 1  # Start index from 1

# Convert sorted list of dictionaries to DataFrame
df = pd.DataFrame(sorted_allData)

fields_to_exclude = ['reviews_count', 'profile_url']  # Replace with the actual fields you want to exclude

# Drop specified fields (columns)
df = df.drop(fields_to_exclude, axis=1)
# Export DataFrame to Excel
df.to_excel('hospital_data.xlsx', index=False)

print("Data has been successfully exported to 'hospital_data.xlsx'")

