import os
import sys,json
from pathlib import Path
import   re

def calculateTotal(items,tax_rate):
    total=0
    for item in items:
      total += item['price']
    total = total*(1+tax_rate)
    return(total)

class userManager:
    def __init__(self,db_url,  timeout=30):
        self.db_url=db_url
        self.timeout =timeout
        self.users=[]

    def GetUser(self, id):
        for u in self.users:
            if u['id']==id:
                return u
        return None

    def add_user(self,name,email,role = 'viewer'):
        user = {'id': len(self.users)+1,'name':name,
            'email': email,
            'role':role}
        self.users.append(user)

def   format_name(first,last,  middle=None):
        if middle:
          return f"{first} {middle} {last}"
        else:
            return f"{first} {last}"

TIMEOUT=30
max_retries =   5
DefaultRole='admin'

def process_items(  items ):
    results=[]
    for i,item in enumerate(items):
        if item['active']==True:
            results.append({'index':i,'value':item['value'],'processed':True,})
    return results
