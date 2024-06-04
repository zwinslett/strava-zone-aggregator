import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
import urllib3

import login as login


# Fetches the access token required to for make requests for your account. Uses values from login.py,
# which is included in the gitignore.See login.example.py for template.
def get_token():
    payload = {
        'client_id': f'{login.client_id}',
        'client_secret': f'{login.client_secret}',
        'refresh_token': f'{login.refresh_token}',
        'grant_type': 'refresh_token',
        'f': 'json'
    }

    print('Requesting Token...\n')
    res = requests.post('https://www.strava.com/oauth/token', data=payload, verify=False)
    access_token = res.json()['access_token']

    header = {'Authorization': 'Bearer ' + access_token}
    return header


# Fetches the activities between two dates represented in epoch timestamps passed as the arguments before and after.
# In case the user wants to request more than 200 activities, this function accounts for pagination.
def get_activities(header, before, after, page):
    # start at page ...
    page = page
    # set new_results to True initially
    new_results = True
    # create an empty array to store our combined pages of data in
    data = []
    while new_results:
        # Give some feedback
        print(f'You are requesting page {page} of your activities data ...')
        # request a page + 200 results
        get_strava = requests.get('https://www.strava.com/api/v3/activities', headers=header, params={'per_page': 200,
                                                                                                      'page': f'{page}',
                                                                                                      'before': before,
                                                                                                      'after': after}).json()
        # save the response to new_results to check if its empty or not and close the loop
        new_results = get_strava
        # add our responses to the data array
        data.extend(get_strava)
        # increment the page
        page += 1
    # return the combine results of our get requests
    return data


# Fetches the zones for a given activity id.
def get_zones(id, header):
    data = requests.get(f'https://www.strava.com/api/v3/activities/{id}/zones', headers=header).json()
    return data


# Converts a pace from decimal minutes per mile to MM:SS format.
def convert_to_mm_ss(pace):
    minutes = int(pace)
    seconds = int((pace - minutes) * 60)
    return f"{minutes:02d}:{seconds:02d}"


# Returns a Pandas series for each pace zone. Converts the paces in Strava's API from meters per second to minutes
# per mile (in decimal form) uses the convert_to_mm_ss() function to format the results in MM:SS. Checks for dividing
# by zero and negative ints.
def convert_pace_zones(row):
    time_dict = {}
    for item in row['distribution_buckets']:
        if item['min'] > 0 and item['max'] > 0:
            min_pace = 60 / (item['min'] * (3600 / 1609.34))
            max_pace = 60 / (item['max'] * (3600 / 1609.34))
            min_pace_str = convert_to_mm_ss(min_pace)
            max_pace_str = convert_to_mm_ss(max_pace)
            column_name = f"{min_pace_str}-{max_pace_str}"
        else:
            if item['min'] < 0:
                max_pace = 60 / (item['max'] * (3600 / 1609.34))
                max_pace_str = convert_to_mm_ss(max_pace)
                column_name = f"> {max_pace_str}"
            else:
                if item['min'] == 0:
                    max_pace = 60 / (item['max'] * (3600 / 1609.34))
                    max_pace_str = convert_to_mm_ss(max_pace)
                    column_name = f"> {max_pace_str}"
                else:
                    min_pace = 60 / (item['min'] * (3600 / 1609.34))
                    min_pace_str = convert_to_mm_ss(min_pace)
                    column_name = f"< {min_pace_str}"

        time_dict[column_name] = item['time']

    return pd.Series(time_dict)


# Returns a Pandas series where each column is a heart rate zones from the distribution_buckets[] in the Strava
# response. Checks for dividing by zero and negative ints.
def convert_heart_zones(row):
    time_dict = {}
    for item in row['distribution_buckets']:
        if item['min'] >= 0 and item['max'] >= 0:
            column_name = f"{item['min']} - {item['max']}"
            time_dict[column_name] = item['time']
        else:
            if item['min'] <= 0:
                column_name = f"{item['max']}"
                time_dict[column_name] = item['time']
            else:
                column_name = f"{item['min']}+"
                time_dict[column_name] = item['time']
    return pd.Series(time_dict)


# Splits a MM-DD-YYYY date into into discrete values (stored in an array) and turns those values into ints. Then passes
# those ints to datetime() in order to get an epoch timestamp.
def get_timestamp(date):
    x = date.split('-')
    for index, item in enumerate(x):
        x[index] = int(item)
    return datetime.datetime(x[2], x[0], x[1], 0, 0, 0).timestamp()


sns.set_theme()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

header = get_token()
# Let the user input a before and after date to be used as arguments in the get_activities function.
before_date = input("Enter the before date in MM-DD-YYYY")
after_date = input("Enter the after date in MM-DD-YYYY")

# Pass the user's inputs as arguments to our get_timestamps function (to convert them to usable Epoch timestamps)
before_timestamp = get_timestamp(before_date)
after_timestamp = get_timestamp(after_date)
activities = get_activities(header, before_timestamp, after_timestamp, 1)

activity_ids = []
# For each object in activities retrieve the value of the id field and store it in the activity_ids array.
for item in activities:
    activity_ids.append(item['id'])

pace_zones = []
heart_zones = []

# iterates over the ids stored in the activity_ids array and passes them to the get_zones function. the response of
# get_zones is an array of objects, so we filter each response where type == pace or heartrate and store those
# objects in their respective arrays.
for item in activity_ids:
    res = get_zones(item, header)
    result_pace = next(filter(lambda x: x['type'] == 'pace', res), None)
    result_pace['id'] = item
    result_heartrate = next(filter(lambda x: x['type'] == 'heartrate', res), None)
    result_heartrate['id'] = item
    pace_zones.append(result_pace)
    heart_zones.append(result_heartrate)

# Set display options for the dataframe in the console.
pd.set_option('display.max_rows', None)  # Show all rows
pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.width', None)  # Adjust the width to avoid line breaks
pd.set_option('display.max_colwidth', None)  # Show full content of each column
pd.set_option('display.float_format', '{:.0f}'.format)  # Setting display option for integers

# Create a data frame from the pace_zones array.
df = pd.DataFrame(data=pace_zones)
# Add a column in the dataframe that sums the time field from each object in the distribution_buckets array.
df['zones_sum'] = df['distribution_buckets'].apply(lambda x: sum(item['time'] for item in x))
# Create a new Pandas series using the convert_pace_zone function as a callback.
pace_series = df.apply(convert_pace_zones, axis=1)
# Merge that new series into dataframe.
df = df.merge(pace_series, left_index=True, right_index=True)
# Drop the Distribution_Buckets column from the dataframe.
df = df.drop(columns='distribution_buckets')
# Create a new row called Total that sums the values in each column.
df.loc['Total'] = df.sum()
# Set the columns in which it doesn't make sense to sum to NaN
df.loc['Total', ['type', 'score', 'resource_state', 'sensor_based', 'id']] = np.nan

# Take the previously used Pandas series of pace zones and put the columns name in a list.
columns_for_pace = pace_series.columns.tolist()
# Create the data we'll use for the pie chart by using the values in Totals for the given columns.
data_for_pace = df.loc['Total', columns_for_pace]
fig, ax = plt.subplots(figsize=(8, 8))
ax.pie(data_for_pace, autopct='%1.1f%%')
ax.legend(labels=columns_for_pace, loc='best', bbox_to_anchor=(.3, .3))
ax.set_title(f'Percentage in each Pace Zone for {after_date} to {before_date}')
plt.savefig('imgs/pace_pie', bbox_inches='tight', dpi=200)

# Rinse and repeat for heart_zones.
df2 = pd.DataFrame(data=heart_zones)
df2['zones_sum'] = df2['distribution_buckets'].apply(lambda x: sum(item['time'] for item in x))
heart_rate_series = df2.apply(convert_heart_zones, axis=1)
df2 = df2.merge(heart_rate_series, left_index=True, right_index=True)
df2 = df2.drop(columns='distribution_buckets')
df2.loc['Total'] = df2.sum()
df2.loc['Total', ['type', 'score', 'resource_state', 'sensor_based', 'id', 'points', 'custom_zones']] = np.nan

columns_for_heartrate = heart_rate_series.columns.tolist()
data_for_heartrate = df2.loc['Total', columns_for_heartrate]
fig2, ax2 = plt.subplots(figsize=(8, 8))
ax2.pie(data_for_heartrate, autopct='%1.1f%%')
ax2.legend(labels=columns_for_heartrate, loc='best', bbox_to_anchor=(.3, .3))
ax2.set_title(f'Percentage in each Heartrate Zone for {after_date} to {before_date}')
plt.savefig('imgs/heart_rate_pie', bbox_inches='tight', dpi=200)

print(df)
print(df2)
