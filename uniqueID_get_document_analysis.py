

import pandas as pd
import shutil
import numpy as np
from uniqueID_document_functions import *

df = pd.read_csv('Purchase Order Labeling Updated - Sheet1.csv', index_col=False)
df['Document_title'] = df['Document_title'].str.strip()
uniqueKeys = df['BOL_Key']

# Delete the folder if it exists
shutil.rmtree('JSON Responses', ignore_errors=True)



#Loads the map of JobID: filename key-value pairs
#Commenting out for testing
job_id_dict = load_json_file('uniqueID_start_document_analysis.txt')


accuracy = calculate_accuracy(job_id_dict, df)

print()
print()
print(f'Textract got {accuracy*100}% of them right')