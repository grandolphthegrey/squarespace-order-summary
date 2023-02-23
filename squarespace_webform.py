#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import datetime
import re
import dateutil.parser
import subprocess
import json
import PySimpleGUI as sg
import pandas as pd
import numpy as np

from operator import itemgetter
from pandas.io.json import json_normalize
from pytz import timezone
from datetime import timedelta as td

#API Key
apikey = ''

#variables to specify dates in GUI
today = datetime.datetime.now() 
order_date = today - td(days=4)  

#Directories
json_dir = '/tmp/out.json'
out_dir = '/tmp/orders.html'
 

#GUI user input window
sg.theme('SystemDefault')
layout = [[sg.Text('\n Please enter the pickup date. Note that orders with no date will be included in query results.')],      
                 #[sg.Text('Orders Placed on Date (Format: YYYY-MM-DD)',size=(30,2)), sg.InputText('{}'.format(order_date.strftime('%Y-%m-%d')))],
                 [sg.Text('Pickup/Delivery Date (Format: YYYY-MM-DD)',size=(40,2)), sg.InputText('{}'.format(today.strftime('%Y-%m-%d')))],
                 [sg.Text('\n')],
                 [sg.Submit(), sg.Cancel()]]      

window = sg.Window('Orders Query', layout)    

#Loop to verify fidelity of user input
while True:   

    try:
        #Read the user input
        event, values = window.read()

        #If the user clicks on Exit, Cancel or exits out of the window, then exit WHILE loop
        if event in ('Exit', 'Cancel', None):
            #print("I want to exit")
            var_exit = 1
            break

        #if the user enters a valid date, exit the WHILE loop
        #if isinstance(datetime.datetime.strptime(values[0], '%Y-%m-%d'), datetime.date) == True and isinstance(datetime.datetime.strptime(values[1], '%Y-%m-%d'), datetime.date) == True and values[0] != values[1]:
        if isinstance(datetime.datetime.strptime(values[0], '%Y-%m-%d'), datetime.date) == True:
            #print('valid dates')
            var_exit = 0
            break

        #If the user enters two equal dates, alert them that this isn't possible
        #if values[0] == values[1]:
        #    sg.popup('Error: The two dates entered cannot be the same date.')
    
    #If the user hasn't entered valid dates, let them know:
    except:
        #print('not valid dates')
        sg.popup('Please enter a valid format')


#values = ['2020-04-07', '2020-04-04']

#var_exit = 2

if var_exit != 1:
    #r = requests.get('https://api.squarespace.com/1.0/commerce/orders?modifiedAfter={a}&modifiedBefore={b}&fulfillmentStatus={d}'.format(a='{}T07:00:00Z'.format(values[0]), b='{}T06:59:00Z'.format(values[1]),d='PENDING'), headers={'Authorization':'Bearer {}'.format(apikey)})
    #r = requests.get('https://api.squarespace.com/1.0/commerce/orders/5e8753571450d10705c25c8e', headers={'Authorization':'Bearer {}'.format(apikey)})
    r = requests.get('https://api.squarespace.com/1.0/commerce/orders?fulfillmentStatus={d}'.format(d='PENDING'), headers={'Authorization':'Bearer {}'.format(apikey)})
    
    #Sort the input
    r_sorted = sorted(r.json()['result'], key=itemgetter('orderNumber'), reverse=True)
    #r_sorted=[r.json()]

    
    #Loop through and get ALL pending orders
    while r.json()['pagination']['hasNextPage'] is True:
        token = r.json()['pagination']['nextPageCursor']

        r = requests.get('https://api.squarespace.com/1.0/commerce/orders?fulfillmentStatus={d}&cursor={e}'.format(d='PENDING', e=token), headers={'Authorization':'Bearer {}'.format(apikey)})
        
        
        r_next = sorted(r.json()['result'], key=itemgetter('orderNumber'), reverse=True)
        
        print('found more orders, will append')
        [r_sorted.append(next_order) for next_order in r_next]
        #r_sorted.append(r_next)
       
    #Save output to JSON
    with open('{}'.format(json_dir), 'w') as f:
        json.dump(r_sorted, f, ensure_ascii=False, indent=4)

    #If there are no orders, let the user know
    if not r_sorted:
        print('no orders in range, yo')
        var_exit = 1
        sg.popup('No pending orders for this date')
    
if var_exit != 1:
      
    #columns for final dataframe
    cols = ['orderNumber','shippingAddress.firstName', 'shippingAddress.lastName','shippingAddress.address1','shippingAddress.address2','shippingAddress.city','shippingAddress.postalCode','createdOn','fulfillmentStatus','productName','final_quantity']
    
    #labels for final two columns in final dataframe
    pickup_header = 'Pickup_Or_Delivery'
    pickupdate_header = 'Pickup_Or_Delivery_Date'
    
    #placeholders for final dataframe and list to hold product options
    final_df = pd.DataFrame()
    opt_cols_list = []
    
    #Loop through each order and extract the relevant information from the JSON output
    for ii, order in enumerate(r_sorted):
        
        #Main table
        main_df = json_normalize(r_sorted[ii])
        
        #get the part of the JSON output that has the item options. Include the orderNumber & variantId for JOIN purposes
        varid = json_normalize(r_sorted[ii],record_path=['lineItems','variantOptions'],meta=['orderNumber',['lineItems','variantId']])
        
        #pivot the options into their own columns -- if there are no options, skip making this table
        if len(varid) > 0:
            varid_pivot = pd.pivot(varid,index='lineItems.variantId',columns='optionName',values='value')
        
            #save the option columns for final data table
            opt_cols = varid['optionName'].drop_duplicates().to_list()
            opt_cols_list = opt_cols_list + opt_cols
        
            #reset the options table and fill in NaNs with blanks
            varid_pivot_reset = varid_pivot.reset_index().fillna('')
        
        #get the products portion of the JSON ouptut
        products = json_normalize(r_sorted[ii],record_path=['lineItems'],meta=['orderNumber'])
        #Rename the "Quantity" column to "final_quantity" in case there is a product option named "quanity"
        products.rename(columns={'quantity':'final_quantity'},inplace=True)
        
        if len(varid) > 0:
            #join the production options with the products table, based on variantId
            merged = pd.merge(varid_pivot_reset, products, how='outer', left_on=['lineItems.variantId'], right_on=['variantId'])
        
        else:
            merged = products
            opt_cols = []
        
        #Get the pickup/delivery options from the JSON response
        ship = json_normalize(r_sorted[ii],record_path=['shippingLines'],meta=['orderNumber'])
        ship = ship.rename(columns={'method':'{}'.format(pickup_header)})
        
        #Get the pick up date from the JSON response
        pickup = json_normalize(r_sorted[ii],record_path=['formSubmission'],meta=['orderNumber'])
        pickup = pickup[pickup['label']=='Date'].rename(columns={'value':'{}'.format(pickupdate_header)})
        pickup.drop('label',1, inplace=True)
        
        #Merge with the Pickup/Delivery table
        merged_1 = pd.merge(merged,ship, on='orderNumber', how='outer')
        
        #Merge with the Pick Up Date table
        merged_2 = pd.merge(merged_1,pickup, on='orderNumber', how='outer')
        
        #Merge with final table
        merged_final = pd.merge(merged_2, main_df, on='orderNumber', how='outer')
        
        #Specify columns to keep
        #print_df = merged_final[cols+opt_cols+[pickup_header]+[pickupdate_header]]
    
        #Append to main df
        final_df = final_df.append(merged_final, ignore_index=True, sort=False)
        #break
    #Specify the columns in the final dataframe
    opt_cols_unique = pd.unique(opt_cols_list).tolist()
    
    final_df = final_df[cols+opt_cols_unique+[pickup_header]+[pickupdate_header]].dropna(axis=1,how='all')#.fillna('')#.sort_values(by=['orderNumber'],axis=0)
    
    #Convert the orderdate column to PDT
    final_df['createdOn'] = [dateutil.parser.parse(item).astimezone(timezone('US/Pacific')).strftime('%Y-%m-%d %I:%M %p') for item in final_df['createdOn']]
    #replace all blanks cells with NaN and drop any remaining columns that are completely blank
    #orders = final_df.replace(r'^\s*$', np.nan, regex=True).dropna(axis=1,how='all').fillna('')
    orders = final_df
    #Save to HTML -- replace the empty Delivery Date cells with NaN so they will be at the bottom of the sorted HTML table
    try:
        orders.replace('--', value=np.nan, inplace=True)
    except Exception as e: 
        print('exception replace --')
        print(e)
        pass
    orders_html = orders.sort_values(by=[pickupdate_header,'orderNumber'],axis=0, na_position='last').to_html()
    
    #Filter DF for delivery and pickup
    pickup_opts = orders[pickup_header].unique().tolist()
    pickups = []
    #Loop through options
    for option in pickup_opts:
        #this line originally referenced values[1]
        df = orders.query('{a} == "{b}" & ({c} == "{d}" | {c}.isnull())'.format(a=pickup_header, b=option, c=pickupdate_header, d=values[0]))
        pickups.append(df)
    
    #If there are no orders for the date specified, let the user know and halt execution of the script
    if all([df.empty for df in pickups]):
        var_exit = 7
        print('no orders')
        sg.popup('No pending orders for this date')
        
    if var_exit != 7:
        #Replace all blank cells with NaNs; query the dataframe and filter by correct date; then drop all columns that have all NaNs.
        #this line originally referenced values[1]
        inventory_df = orders.replace(r'^\s*$', np.nan, regex=True).query('{c} == "{d}"'.format(c=pickupdate_header, d=values[0])).dropna(axis=1,how='all').fillna('')
        inventory_df_nodates = orders.replace(r'^\s*$', np.nan, regex=True).query('{c}.isnull()'.format(c=pickupdate_header, d=values[0])).dropna(axis=1,how='all').fillna('')
        
        try:
            #Get the necessary columns to aggregate by groupby method
            inv_cols = inventory_df.loc[:,'productName':pickup_header].iloc[:,0:-1].columns.tolist()
            inv_cols_nodates = inventory_df_nodates.loc[:,'productName':pickup_header].iloc[:,0:-1].columns.tolist()
            inv_cols.remove('final_quantity')
            inv_cols_nodates.remove('final_quantity')
    
            #Generate a dataframe with total quantity of items
            inventory_df = inventory_df.groupby(inv_cols).final_quantity.sum().to_frame()
            inventory_df_nodates = inventory_df_nodates.groupby(inv_cols_nodates).final_quantity.sum().to_frame()
    
        except Exception as e: 
            print('replace NaNs')
            print(e)
            pass
        
        #save to HTML
        #inventory_html = inventory_df.to_html()
        
        #Pipe output tables to web browser
        with open('/tmp/orders.html', 'w') as f:
            #This line originally referenced values[1]
            f.write(r'<h1 align="center"> Pending Orders for {}</h1>'.format(values[0]))
            f.write(r'<br>')
            for ii,option in enumerate(pickup_opts):
                f.write(r'<h2 align="center">{}</h2>'.format(option))
                #Drop fullfilment status column
                pickups[ii] = pickups[ii].drop('fulfillmentStatus',axis=1)
                #replace all blanks with NaNs
                pickups[ii] = pickups[ii].replace(r'^\s*$', np.nan, regex=True)
                #Replace NaNs in date column with "--"
                pickups[ii].loc[:,pickupdate_header] = pickups[ii].loc[:,pickupdate_header].fillna('--')
                #Drop columns that only contain NaNs
                pickups[ii] = pickups[ii].dropna(axis=1, how='all')
                #fill remaining NaN cells with a blank string
                pickups[ii] = pickups[ii].fillna('')
    
                #Shorten column names
                pickups[ii].columns = [name.replace('shippingAddress',"") for name in pickups[ii].columns]
    
                #if the table getting created is not for delivery, drop the address columns
                if re.search('delivery', pickup_opts[ii], re.IGNORECASE) is None:
                    #pickups[ii].remove('Pickup_Or_Delivery')
                    try:
                        pass
                        pickups[ii] = pickups[ii].drop('.address1',axis=1)
                        pickups[ii] = pickups[ii].drop('.city',axis=1)
                        pickups[ii] = pickups[ii].drop('.postalCode', axis=1)
                        pickups[ii] = pickups[ii].drop('.address2',axis=1)
                    except Exception as e: 
                        print(e)
                        pass
                
                #set a multi-index
                try:
                    pickups[ii] = pickups[ii].set_index(pickups[ii].loc[:,:'createdOn'].columns.tolist())
                    f.write(pickups[ii].sort_values(['Pickup_Or_Delivery_Date', 'orderNumber'], ascending=[False, True]).to_html())
                    f.write(r'<br>')
                except Exception as e:
                    print(e)
                    pass
                
            #Write inventory summary heading to HTML file
            #this line originally referenced values[1]
            f.write(r'<h1 align="center"> Pending Inventory Summary</h1>')
            f.write(r'<br>')
            f.write(r'<h2 align="center"> Orders for {}</h2>'.format(values[0]))
            f.write(r'<br>')
            #Write inventory DF to file
            f.write(inventory_df.to_html())
            f.write(r'<br>')
            f.write(r'<h2 align="center"> Dateless Orders</h2>')
            f.write(inventory_df_nodates.to_html())
            
            
        subprocess.run(['open', '{}'.format(out_dir)])
    
