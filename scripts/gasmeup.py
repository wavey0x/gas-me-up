
from brownie import chain, Contract, convert
from brownie.network.event import EventLookupError
from brownie.network.web3 import _resolve_address
from ..my_details import handle, my_addresses
from pprint import pprint
import os, csv, requests, pandas, click
from datetime import datetime


def read_checkpoint(address):
    try:
        with open(f'checkpoints/{address}.csv','r') as checkpoints:
            rows = csv.reader(checkpoints)
            rows = rows
            for row in rows:
                startBlock = int(row[0]) + 1
        print(f"last checkpoint at block {startBlock}")
        return startBlock
    except FileNotFoundError:
        print('no checkpoint found, starting from block 0')
        return 0

def checkpoint(address, block):
    with open(f'checkpoints/{address}.csv','w') as checkpoints:
        writer = csv.writer(checkpoints)
        writer.writerow((str(block),None))
    print(f"checkpoint for {address} set to block {block}")

def fetch_txs(address, startBlock):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock={startBlock}&sort=asc&apikey={os.environ['ETHERSCAN_TOKEN']}"
    response = requests.get(url).json()['result']
    for item in response:
        item['tx_type'] = 'transaction'
        item['from'] = convert.to_address(item['from'])
    df = pandas.DataFrame(response)
    if(len(df)) > 0:
        return df[df['from'] == address]
    return df

def fetch_internal_txs(address, startBlock):
    url = f"https://api.etherscan.io/api?module=account&action=txlistinternal&address={address}&startblock={startBlock}&sort=asc&apikey={os.environ['ETHERSCAN_TOKEN']}"
    response = requests.get(url).json()['result']
    for item in response:
        item['tx_type'] = 'internal'
        item['from'] = convert.to_address(item['from'])
    df = pandas.DataFrame(response)
    if(len(df)) > 0:
        return df[df['from'] == address]
    return df

def fetch_filtered_txs_list():
    addresses = [_resolve_address(address) for address in my_addresses]
    df = None
    for address in addresses:
        print(address)
        startBlock = read_checkpoint(address)
        txs = fetch_txs(address, startBlock)
        internal_txs = fetch_internal_txs(address, startBlock)
        all = txs.append(internal_txs)
        
        df = all if df is None else df.append(all)
        counter = len(df)
        print(df.columns)
        for i, row in df.iterrows():
            hash = row['hash']
            receipt = chain.get_transaction(hash)
            fn_name = receipt.fn_name
            print(' ')
            print(f"hash: {hash}")
            print(f"timestamp: {datetime.utcfromtimestamp(int(row['timeStamp']))} UTC")
            if fn_name == 'approve':
                event = receipt.events['Approval'][0]
                token = Contract(event.address)
                symbol = token.symbol()
                try:
                    spender = Contract(event['_spender'])
                except EventLookupError:
                    try:
                        spender = Contract(event['spender'])
                    except EventLookupError:
                        spender = Contract(event['guy'])
                
                print(spender)
                print(f"approved token {symbol} to {spender.__dict__['_build']['contractName']} {spender}")
            else:
                print(f"called function: {fn_name}")
                try:
                    to = Contract(row['to'])
                except (UnboundLocalError, ValueError):
                    to = row['to']
                if len(fn_name) > 0:
                    print(f"on contract: {to.__dict__['_build']['contractName']} {to}")
                else:
                    print(f"to: {to.__dict__['_build']['contractName']} {to}")
            print(' ')
            keep = click.confirm('Should this tx be reimbursed?')
            if not keep:
                df.drop(i)
            counter -= 1
            print(f"{counter} remaining")

        if len(df) > 0:
            endBlock = all['blockNumber'].max()
            checkpoint(address,endBlock)
        else:
            print('no new reimbursement txs for this address')
    return df

def main():
    df = fetch_filtered_txs_list()
    print(df)
    counter = len(df)
    print(df.columns)
    
    df.to_csv(f'pending/{handle}.csv', 'w', index=False)