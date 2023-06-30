import boto3
import json
import io
import os
import fitz
from datetime import datetime
from PIL import Image, ImageDraw


def get_file_paths(folder_path):
    file_paths = []

    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            relative_path = os.path.relpath(os.path.join(root, file_name), folder_path)
            file_paths.append(relative_path)

    return file_paths

def convert_pdf_to_bytes(pdf_file_path):
    with open(pdf_file_path, 'rb') as file:
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        pdf_bytes = pdf.read()
    return pdf_bytes

client = boto3.client('textract')
bucket = "circle-textract"
name = "BOL/BOL_PO-B1048409 (1).pdf"

document = {
    "S3Object": {
        "Bucket": bucket,
        "Name": name
    }
}

queries_config = [
    {
        "Text": "What is the dispatch from address?",
        "Alias": "PICKUP_ADDRESS"
    },
    {
        "Text": "What is the ship to address?",
        "Alias": "DELIVERY_ADDRESS"
    },
    {
        "Text": "What is the Bill of Lading ID?",
        "Alias": "BOL_ID"
    },
    {
        "Text": "What is the Bill To address?",
        "Alias": "BILL_TO"
    },
    {
        "Text": "What is the trailer ID?",
        "Alias": "TRAILER_ID"
    },
    {
        "Text": "What is the seal number?",
        "Alias": "SEAL_ID"
    }
]

response = client.analyze_document(
    Document=document,
    FeatureTypes=['QUERIES'],
    QueriesConfig={
        'Queries': queries_config
    }
)
with open('data.json', 'w') as f:
    json.dump(response, f)


def get_query_results(response):
    # Initialize an empty dictionary to store query results
    query_results = {}

    # Loop through each block in the response
    for block in response["Blocks"]:
        # Check if the block is a QUERY block
        if block["BlockType"] == "QUERY":
            # Get the query text and alias
            query_text = block["Query"]["Text"]
            query_alias = block["Query"]["Alias"]
            
            # Check if the block has any relationships
            if "Relationships" in block:
                # Loop through the block's relationships to find matching ANSWER blocks
                for relationship in block["Relationships"]:
                    if relationship["Type"] == "ANSWER":
                        # Loop through the ANSWER blocks to extract the text and confidence score
                        for answer_id in relationship["Ids"]:
                            for answer_block in response["Blocks"]:
                                if answer_block["Id"] == answer_id and answer_block["BlockType"] == "QUERY_RESULT":
                                    query_results[query_alias] = {"response": answer_block["Text"], "confidence": answer_block["Confidence"]}
                                    break
    return query_results

# Print the query results
print(get_query_results(response))



# Load the S3 client
s3 = boto3.client('s3')

# download the PDF document from S3
mys3object = s3.get_object(Bucket=bucket, Key=name)
document_content = mys3object['Body'].read()

# open the PDF document using PyMuPDF
pdf = fitz.open(stream=document_content, filetype="pdf")

def highlight_response_fields_pdf(response, pdf):
    # iterate through each block in the Textract response
    for block in response['Blocks']:
    # if the block is of type 'QUERY', extract the bounding box coordinates and draw a rectangle around the corresponding area in the PDF
        if block['BlockType'] == 'QUERY_RESULT' and 'Geometry' in block:
            bbox = block['Geometry']['BoundingBox']
            page = pdf[0]
            rect = fitz.Rect(bbox['Left'] * page.rect.width, bbox['Top'] * page.rect.height, (bbox['Left'] + bbox['Width']) * page.rect.width, (bbox['Top'] + bbox['Height']) * page.rect.height)
            print(rect)
            highlight = page.add_highlight_annot(rect)

highlight_response_fields_pdf(response, pdf)


def highlight_response_fields(response, image):
    # create a copy of the image to draw on
    draw = ImageDraw.Draw(image)

    # iterate through each block in the Textract response
    for block in response['Blocks']:
        # if the block is of type 'QUERY', extract the bounding box coordinates and draw a rectangle around the corresponding area in the image
        if block['BlockType'] == 'QUERY_RESULT' and 'Geometry' in block:
            bbox = block['Geometry']['BoundingBox']
            img_width, img_height = image.size
            left = img_width * bbox['Left']
            top = img_height * bbox['Top']
            width = img_width * bbox['Width']
            height = img_height * bbox['Height']
            rect = (left, top, left+width, top+height)
            draw.rectangle(rect, outline='red')
    
    return image



def timestamp():
    now = datetime.now()
    return now.strftime('%Y-%m-%d-%H-%M-%S')

# save the modified PDF document
file_name = 'box_drawn_' + timestamp() + '.pdf'
output_key = 'output/'+file_name

# Save the modified PDF object to S3
with io.BytesIO() as pdf_bytes:
    pdf.save(pdf_bytes)
    pdf_bytes.seek(0)
    s3.upload_fileobj(pdf_bytes, bucket, output_key)  

