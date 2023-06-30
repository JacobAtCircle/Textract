import boto3
import json
import io
import base64
import json
import time
import os
import fitz
from datetime import datetime
from PIL import Image, ImageDraw
import random

s3 = boto3.client('s3')
textract = boto3.client('textract')
bucket = 'circle-textract'
prefix = 'PO'
jobID_to_filename_map = {}

uniqueIDs = ['PO', 'ORD', 'SN', 'REQID', 'PRO', 'OURREF', 'SO', 'BOL', 
             'SHIPID', 'MC', 'PICKUPNUM', 'TRIPID', 'ID', 'DR', 'LN', 
             'JOBNAME', 'SD', 'LOADNUM', 'JOBNUM', 'EWR', 'REF', 
             'UFLNUM', 'LOADID', 'OMEGAJOBNUM', 'ULFNUM']

def load_json_file(file_path):
    with open(file_path, 'r') as file:
        json_data = json.load(file)
        return json_data

queries_config = load_json_file('queries_uniqueid.json')


def save_dictionary_to_file(dictionary, filename):
    with open(filename, 'w') as file:
        json.dump(dictionary, file)

#This function gets a list of all the files that are in the S3 bucket. At the end, it only takes 10 random entries from that list for testing purposes.
def get_s3_bucket_files(bucket_name, subfolder, s3):
    file_names = []
    # List all objects in the bucket
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=subfolder)
    # Retrieve the file names from the response
    for obj in response['Contents']:
        file_names.append(obj['Key'])
    #Don't want to include the subfolder itself in list, hence [1:]
    file_names = file_names[1:]
    # Shuffle the list of file names
    random.shuffle(file_names)
    # Return the first 10 file names, just because it's good to test them in small batches first as to not run up the costs.
    return file_names[:10]

def start_document_analysis(textract, bucket_name, object_key, map):

    response = textract.start_document_analysis(
        DocumentLocation={
            'S3Object': {
                'Bucket': bucket_name,
                'Name': object_key,
            }
        },
        FeatureTypes=[
            'QUERIES'
            ],
        QueriesConfig={
            'Queries':queries_config
        }
    )

    job_id = response['JobId']
    map[job_id] = object_key  # Store the JobId and document file name mapping
    print(f"Processing job {job_id} for document at {object_key}")


#First, get a list of all the filenames in the desired 'S3' bucket.
PO_filenames = get_s3_bucket_files(bucket, prefix, s3)
print(PO_filenames)
#For each file in the list, textract starts the analysis and assigns each document a JobID. Then, the JobID is mapped to the filename
#of each document and saved as a dictionary jobID_to_filename_map. 
for file in PO_filenames:
    start_document_analysis(textract, bucket, file, jobID_to_filename_map)

#Saves the dictionary as a text file so that it can be used to get the expense analysis for each document by indexing their title.
save_dictionary_to_file(jobID_to_filename_map, 'uniqueID_start_document_analysis.txt')
