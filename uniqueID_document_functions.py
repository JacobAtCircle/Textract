import math
import json
import os
import boto3
import re


def is_nan(value):
    try:
        float_value = float(value)
        return math.isnan(float_value)
    except (ValueError, TypeError):
        return False


def load_json_file(filename):
    with open(filename, 'r') as file:
        data = json.load(file)
    return data

#Gets the result, returns an array of the query responses, and saves the responses as filenames from original document
def get_query_results(job_id, job_id_dict):
    textract_client = boto3.client('textract')

    # Call Textract API to get the document analysis response
    response = textract_client.get_document_analysis(JobId=job_id)
    query_results = {}


    # Parse the response for query results
    blocks = response.get('Blocks', [])
    for block in blocks:
        if block.get('BlockType') == 'QUERY_RESULT':
            query_text = block.get('Text')
            confidence = block.get('Confidence')
            query = None
         
            has_number = bool(re.search(r'\d', query_text))
            valid_chars = all(char != '$' and char != '.' for char in query_text)
            #Filters out the obviously wrong 'UniqueID' results with the criteria below:
            if query_text is not None and (len(query_text) >= 5 and len(query_text) <= 12) and has_number and valid_chars:
                text_id = block.get('Id')
                

                # Iterate through the blocks
                for block in blocks:
                    if block.get('BlockType') == 'QUERY':   
                        # Iterate through the Relationships
                        for relationship in block.get("Relationships", []):
                            if text_id in relationship["Ids"]:
                                # Access the text attribute of the Query
                                query = block["Query"]["Text"]



                if query_text in query_results:
                    # If the query text already exists, compare the confidence scores
                    if confidence > query_results[query_text][0]:
                        # Update with the higher confidence score
                        query_results[query_text] = [confidence, query]
                else:
                    # Add the query text as a new key
                    query_results[query_text] = [confidence, query]


    # Save response object as a JSON string
    response_json = json.dumps(response, indent=4)

    # Get the filename from the job_id_dict and replace forward slash with underscore
    filename = job_id_dict.get(job_id).replace('/', '_')

    # Create the directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "JSON Responses")
    os.makedirs(output_dir, exist_ok=True)

    # Save the JSON string to a file in the output directory
    output_path = os.path.join(output_dir, f"{filename}.json")
    with open(output_path, 'w') as file:
        file.write(response_json)

    return query_results

# a rudimentary way of hard-coding a ranking system for the result. The code below acts as a patchinko machine 
# based on the tags and confidence scores
def fine_tune_the_result(invoice_numbers, highest, highest_conf):

    # Same thing for 'PO:'
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'PO:' and value[0] == highest_conf:
            highest = key
            break

    # Check to see if 'BOL:' was ever a query that got a response because that tends to be the trump card
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'ID:' and value[0] >= 96.0:
            highest = key
            break

    # Same thing for 'Reference:'
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'Reference:' and value[0] == highest_conf:
            highest = key
            break

    # Same thing for 'JOBNUM:'
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'JOBNUM:' and value[0] >= 78.0:
            highest = key
            break

    # Same for 'LOADID:'
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'LOADID:' and value[0] == highest_conf:
            highest = key
            break

    # Check to see if 'BOL:' was ever a query that got a response because that tends to be the trump card
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'BOL:' and value[0] == highest_conf:
            highest = key
            break

    # Check to see if 'BOL:' was ever a query that got a response because that tends to be the trump card
    for key, value in invoice_numbers.items():
        if len(value) >= 2 and value[1] == 'Bill Of Lading:':
            highest = key
            break

    return highest

def calculate_accuracy(job_id_dict, df):
    got_right = 0
    count = 0

    for job_id, document_title in job_id_dict.items():
        print(job_id, document_title)
        reftitle = document_title[3:-4]
        invoice_numbers = get_query_results(job_id, job_id_dict)
        actualID = df.loc[df['Document_title'] == reftitle, 'BOL_Number'].values[0]
        print(f"Document: {document_title}")
        print(f'UniqueIDsFound: {invoice_numbers}')

        if invoice_numbers:
            highest = max(invoice_numbers, key=invoice_numbers.get)
            highest_conf = max(value[0] for value in invoice_numbers.values())
        else:
            highest = float('nan')

        fine_tune_the_result(invoice_numbers, highest, highest_conf)

        print(f'Textract Guess: {highest} Actual ID: {actualID}')
        print()
        print()

        if highest == actualID or is_nan(actualID):
            got_right += 1
        count += 1

    accuracy_ratio = got_right / count
    return accuracy_ratio