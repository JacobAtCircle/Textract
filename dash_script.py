import base64
import io
import mimetypes
import dash
import boto3
import json
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output, State
from PIL import Image, ImageDraw
import fitz


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
#
client = boto3.client('textract')
# Load the S3 client
s3 = boto3.client('s3')


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
    return pdf

def allowed_file(filename):
    return True


app.layout = html.Div([
    dbc.Row([
        dbc.Col(
            html.Div([
                html.H1("Textract Demo"),
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select Files')
                    ]),
                    style={
                        'width': '60%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px'
                    },
                    multiple=False
                ),
                # Add this html.Div to display the name of the file(s) uploaded
                html.Div(id='upload-filename'),
                html.Br(),
                html.Button('Analyze', id='analyze-button', n_clicks=0),
                html.Br()
            ]),
            width=4
        ),
    ]),
    dbc.Row([ 
        dbc.Col([
            html.Div(id='output-image')
        ]),
        dbc.Col([
            dcc.Textarea(
                id='textarea',
                value='''[
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
                ]''',
                style={'width': '50%', 'height': 800},
            )
        ])
    ], justify='center'),
    dcc.Store(id='file-state', data='')
])






@app.callback(Output('upload-filename', 'children'),
              Input('upload-data', 'filename'))
def update_upload_filename(filename):
    if filename is not None:
        return html.Span(filename, style={'fontWeight': 'bold'})
        


@app.callback([Output('output-image', 'children'),
              Output('file-state', 'data')],
              [Input('analyze-button', 'n_clicks')],
              [State('upload-data', 'contents'),
               State('upload-data', 'filename'),
               State('file-state', 'data'),
               State('textarea', 'value')])
def update_output(n_clicks, contents, filename, file_state, query):
    #print(query)
    if n_clicks is not None and file_state == filename:
        n_clicks = None
        return '', filename

    if contents:
        file_type = filename.split('.')[-1]
        if allowed_file(file_type):
            decoded = base64.b64decode(contents.split(',')[1])
            if file_type == 'pdf':
                print(type(decoded))
            else:
                image = Image.open(io.BytesIO(decoded))
            #rotated_image = rotate_image(image)
            #Stuff happens to the image here
            json_query = json.loads(query)
            
            
            response = client.analyze_document(
                Document={'Bytes': decoded},
                FeatureTypes=['QUERIES'],
                QueriesConfig={
                    'Queries': json_query
                }
            )
            query_results = get_query_results(response)
            print(query_results)
            
            # open the PDF document using PyMuPDF
            pdf = fitz.open(stream=decoded, filetype="pdf")
            highlighted = highlight_response_fields_pdf(response, pdf)

            output_stream = io.BytesIO()
            highlighted.save(output_stream)
            pdf_bytes = output_stream.getvalue()
            # encode the bytearray as base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            print('ok')

            return html.Iframe(
                        id='pdf-viewer',
                        src=f"data:application/pdf;base64,{pdf_base64}",
                        width='100%',
                        height='1000px',
                        hidden=False  # set hidden to False when the PDF is ready to be displayed
                    ), filename
        else:
            return 'Invalid file type. Please upload a pdf, jpeg, or png file.', filename
    else:
        return 'Please upload a file.', filename

if __name__ == '__main__':
    app.run_server(debug=True)