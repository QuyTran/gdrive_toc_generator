import os
import argparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

# Instantiate the parser and give it a description that will show before help
parser = argparse.ArgumentParser(description='My Parser')

# Add arguments to the parser
parser.add_argument('--app', dest='app', type=str, help='application name')

# Run method to parse the arguments
args = parser.parse_args()

# Print the result
print (("Your application name is %s") % (args.app))


if args.app == "" or args.app is None:
   appName = "DEFAULT"
else:
   appName = args.app

toc_document_id = config[appName]["toc_document_id"]
folder_id = config[appName]["root_folder_id"]


# {
#     'name',
#     'startIndex',
#     'endIndex',
#     'link' : 'webViewLink',
#     'heading',
#     'id'
# }
def scan_folders(
    drive_service: Resource,
    parent_name: str,
    folder_id: str,
    level: int
    #  , start_index
    ,
    list:list,
):
    global start_index
    query = f"'{folder_id}' in parents and trashed = false"
    #query = ''
    page_token = None
    while True:
        # pylint: disable=maybe-no-member
        response = (
            drive_service.files()
            .list(
                q=query,
                spaces="drive",
                supportsAllDrives="true",
                includeItemsFromAllDrives="true",
                fields="nextPageToken, " "files(id, name, kind, mimeType, webViewLink)",
                pageToken=page_token,
            )
            .execute()
        )

        for file in response.get("files", []):
            # Process change
            tabs = ""
            for i in range(0, level):
                tabs += "\t"
            # list_of_owners = ""
            # if file.get("owners"):
            #     for owner in file.get("owners"):
            #         list_of_owners += owner["displayName"] + ", "

            file_name = tabs + file.get("name")+ "\n"
            end_index = len(file_name) + start_index
            list.append(
                {
                    "start_index": start_index,
                    "end_index": end_index,
                    "heading": level,
                    "parent_name": parent_name,
                    "name": file_name,
                    "link": file.get("webViewLink"),
                    "id": file.get("id"),
                }
            )
            start_index = end_index
            if file.get("mimeType") == "application/vnd.google-apps.folder":
                scan_folders(
                    drive_service,
                    parent_name + "/" + file.get("name"),
                    file.get("id"),
                    level + 1,
                    # start_index=start_index,
                    list=list,
                )
        # files.extend(response.get('files', []))
        page_token = response.get("nextPageToken", None)
        if page_token is None:
            break


def authorize() -> tuple[Resource,Resource]:
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        # "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())


    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    return docs_service, drive_service


def read_content_by_id(docs_service: Resource, toc_document_id: str) -> list:
    doc = docs_service.documents().get(documentId=toc_document_id).execute()
    return doc


def write_content(docs_service: Resource, toc_document_id: str, requests: list) -> list:
    result = (
        docs_service.documents()
        .batchUpdate(documentId=toc_document_id, body={"requests": requests})
        .execute()
    )
    return result

# find the max index and delete it
def build_content_for_delete(doc: list) ->list:
    last_item = doc["body"]["content"][-1]['endIndex']
    if (last_item == 2):
        return []

    return [{
        "deleteContentRange": {
            "range": {
                "startIndex": 1,
                "endIndex": last_item - 1,
            }
        }
    }]

def build_content_for_update_style(doc: list) -> list:
    last_item = doc["body"]["content"][-1]['endIndex']
    if (last_item == 2):
        return []

    return [        
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": 1,
                    "endIndex": last_item - 1,
                },
                "textStyle": {
                    "fontSize": {"magnitude": 12, "unit": "PT"},
                    'weightedFontFamily': {
                        'fontFamily': 'Times New Roman'
                    },
                    "foregroundColor": {
                        "color": {
                            "rgbColor": {"blue": 0.4, "green": 0.2, "red": 0.0}
                        }
                    },
                },
                "fields": "foregroundColor,fontSize, weightedFontFamily",
            }
        }
    ]
    
    

# {
#     "insertText": {
#       "text": "Sample3\n",
#       "location": {
#         "index": 1
#        }
#     }
# },
# {
#     "updateParagraphStyle": {
#       "range": {
#           "startIndex": 1,
#           "endIndex": 8
#        },
#       "paragraphStyle": {
#            "namedStyleType": "HEADING_1"
#       },
#        "fields": "namedStyleType"
#       }
# },
# {
#     "updateTextStyle": {
#     "range": {
#         "startIndex": 9,
#         "endIndex": 16
#     },
#     "textStyle": {
#         "link": {
#         "url": "https://www.google.com"
#         }
#     },
#     "fields": "link"
# }
def build_formatted_list(list:list) -> list:
    formatted_list = []
    for item in list:
        formatted_list.append(
            {
                "insertText": {
                    "text": item["name"],
                    "location": {"index": item["start_index"]},
                }
            }
        )
        formatted_list.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": item["start_index"],
                        "endIndex": item["end_index"],
                    },
                    "paragraphStyle": {
                        "namedStyleType": "HEADING_" + ("6" if item["heading"] > 6 else str(item["heading"]))
                    },
                    "fields": "namedStyleType",
                }
            }
        )
        formatted_list.append(
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": item["start_index"],
                        "endIndex": item["end_index"],
                    },
                    "textStyle": {
                        "link": {"url": item["link"]},
                        
                    },
                    "fields": "link",
                }
            }
        )

    formatted_list.append(
        {
            "createParagraphBullets": {
                "range": {"startIndex": 1, "endIndex": item["end_index"] - 1},
                "bulletPreset": "NUMBERED_DECIMAL_NESTED",
            },
        },    
    )

    return formatted_list

print('1. Authorizing\n')
docs_service, drive_service = authorize()
doc = read_content_by_id(docs_service, toc_document_id)

print('2. Deleting the old content\n')
delete_request = build_content_for_delete(doc)
if delete_request:
    write_content(docs_service, toc_document_id, requests=delete_request)

print('3. Building content based on the root folder structure\n')
list = []
start_index = 1
scan_folders(
    drive_service=drive_service,
    parent_name="/",
    folder_id=folder_id,
    level=1,
    # start_index=1,
    list=list,
)

formatted_list = build_formatted_list(list)
write_content(docs_service, toc_document_id, formatted_list)

print('4. Updating file style')
doc = read_content_by_id(docs_service=docs_service, toc_document_id=toc_document_id)
updated_request = build_content_for_update_style(doc=doc)
if updated_request:
    write_content(docs_service, toc_document_id, requests=updated_request)
