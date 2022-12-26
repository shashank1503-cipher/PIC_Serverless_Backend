from utils import check_user_exist_using_id, check_user_exists_using_email, create_notification
from auth import verify
import asyncio
import json
import pymongo
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
import auth
from firebase_admin import auth as admin_auth
from mangum import Mangum
from dotenv import load_dotenv

import os
# from .db import read, read_one, create, update, delete
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()
MONGO_URI = os.environ.get('MONGO_URI')
client = pymongo.MongoClient(MONGO_URI)
db = client["partnersInCrime"]

app = FastAPI()
handler = Mangum(app)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


"""
---------------------------------------------------------------------
Main Page 
---------------------------------------------------------------------
"""


@app.get('/firsttimelogin')
def first_time_login(req: Request):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    result = {}
    fetch_skills = fetch_user.get("skills", None)
    if not fetch_skills or not len(fetch_skills) > 0:
        result["data"] = True
    else:
        result["data"] = False
    return result


"""
------------------------------------------------------------------------
Search Section
------------------------------------------------------------------------
"""


@app.get("/suggestions")
def autocomp(q):
    pipeline = [
        {
            '$search': {
                'index': 'autodefault',
                "autocomplete": {
                    "query": q,
                    "path": 'name',
                    "tokenOrder": "sequential"
                }
            }
        },
        {
            '$limit': 10
        },
        {
            '$project': {
                "name": 1
            }
        }
    ]
    count = 0

    collections = db["users"]
    aggregated_result = collections.aggregate(pipeline)
    result = {}
    data = []
    for i in list(aggregated_result):
        count += 1
        print(i)
        data.append({"name": i["name"]})
    skillCollection = db['skills']
    pipeline[-1] = {
        '$project': {
            "name": 1,
            "subskills": 1
        }
    }

    aggregated_result = skillCollection.aggregate(pipeline)
    for i in list(aggregated_result):
        count += 1
        data.append({"name": i["name"]})
        subskills = i.get("subskills", [])
        for j in subskills:
            if j:
                count += 1
                data.append({"name": j})
    hashmap = {}
    for i in data:
        hashmap[i["name"]] = i
    result["data"] = [hashmap[k] for k in hashmap]
    result["meta"] = {"total": count}
    return result


@app.get("/skillssuggestions")
def autocompleteskill(q):
    pipeline = [
        {
            '$search': {
                'index': 'autodefault',
                "autocomplete": {
                    "query": q,
                    "path": 'name',
                    "tokenOrder": "sequential"
                }
            }
        },
        {
            '$limit': 10
        }, {
            '$project': {
                "name": 1,
                "subskills": 1
            }
        }
    ]
    count = 0
    data = []
    result = {}
    skillCollection = db['skills']
    aggregated_result = skillCollection.aggregate(pipeline)
    for i in list(aggregated_result):
        count += 1
        data.append({"name": i["name"]})
        subskills = i.get("subskills", [])
        for j in subskills:
            if j:
                count += 1
                data.append({"name": j})
    hashmap = {}

    for i in data:
        hashmap[i["name"]] = i
    result["data"] = [hashmap[k] for k in hashmap]
    result["meta"] = {"total": count}
    return result


@app.get('/searchmessage')
def search_message(q):
    count = db.users.count_documents({"name": {"$regex": q, "$options": "i"}})
    cursor = db.users.find({"name": {"$regex": q, "$options": "i"}})
    res = {}
    res["meta"] = {}
    res["data"] = []
    for i in list(cursor):
        i["_id"] = str(i["_id"])
        res["data"].append(i)
    res["meta"] = {"count": count}
    return res


@app.get("/profile/{id}")
def get_profile(req: Request, id):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid Project Id")
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_profile = db['users'].find_one({"_id": ObjectId(id)})
    fetch_profile['_id'] = str(fetch_profile['_id'])
    if not fetch_profile:
        raise HTTPException(status_code=400, detail="Profile Not Found")
    result = {}
    result['meta'] = {'profile_id': str(fetch_profile['_id'])}
    result["data"] = fetch_profile
    return result


"""
------------------------------------------------------------------------
Project Section
------------------------------------------------------------------------
"""


@app.post("/addproject")
async def add_project(req: Request):
    user = None
    authorization = req.headers.get("Authorization")
    try:
        id_token = authorization.split(" ")[1]
        user = admin_auth.verify_id_token(id_token)
    except Exception as e:
        print(e)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    result = {}
    print(fetch_user['_id'])
    result['user_id'] = ObjectId(fetch_user['_id'])
    result['name'] = fetch_user.get("name", None)
    result['email'] = fetch_user.get("email", None)
    result['image'] = fetch_user.get("photo", None)
    data = await req.body()
    if data:
        data = json.loads(data)
    result['hero_image'] = data.get("image_url", None)
    result['title'] = data.get("title", None)
    if not result['title']:
        raise HTTPException(status_code=400, detail="Please Enter Title")
    result['description'] = data.get("description", None)
    if not result['description']:
        raise HTTPException(status_code=400, detail="Please Enter Description")
    result['idea'] = data.get("idea", None)
    if not result['idea']:
        raise HTTPException(status_code=400, detail="Please Enter Idea")
    result['required_skills'] = data.get("skills", None)
    if not result['required_skills']:
        raise HTTPException(status_code=400, detail="Please Enter Skills")

    try:
        collection = db["projects"]
        fetch_inserted_project = collection.insert_one(result)
        fid = str(fetch_inserted_project.inserted_id)
        result.pop("_id")
        result.pop("user_id")
        return {"meta": {"inserted_id": fid}, "data": result}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Adding Project")


@app.put("/project/{id}")
async def update_project(req: Request, id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid Project Id")
    user = None
    authorization = req.headers.get("Authorization")
    try:
        id_token = authorization.split(" ")[1]
        user = admin_auth.verify_id_token(id_token)
    except Exception as e:
        print(e)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_user_id = fetch_user.get("_id", None)
    fetch_project = db["projects"].find_one({"_id": ObjectId(id)})
    if not fetch_project:
        raise HTTPException(status_code=404, detail="No Project Found")
    if fetch_user_id != fetch_project.get("user_id", None):
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await req.body()
    if not data:
        raise HTTPException(status_code=400, detail="No Data Found")
    data = json.loads(data)
    result = {}
    fetch_hero_image = data.get("image_url", None)
    if fetch_hero_image:
        result['hero_image'] = fetch_hero_image
    fetch_title = data.get("title", None)
    if fetch_title:
        result['title'] = fetch_title
    fetch_description = data.get("description", None)
    if fetch_description:
        result['description'] = fetch_description
    fetch_idea = data.get("idea", None)
    if fetch_idea:
        result['idea'] = fetch_idea
    fetch_required_skills = data.get("skills", None)
    if fetch_required_skills:
        result['required_skills'] = fetch_required_skills
    try:
        collection = db["projects"]
        collection.update_one({"_id": ObjectId(id)}, {"$set": result})
        return {"meta": {"updated_id": id}, "data": result}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Updating Project")


@app.delete("/project/{id}")
def delete_project(req: Request, id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid Project Id")
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_user_id = fetch_user.get("_id", None)
    fetch_project = db["projects"].find_one({"_id": ObjectId(id)})
    if not fetch_project:
        raise HTTPException(status_code=404, detail="No Project Found")
    if fetch_user_id != fetch_project.get("user_id", None):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        collection = db["projects"]
        fetch_deleted_project = collection.delete_one({"_id": ObjectId(id)})
        return {"meta": {"deleted_id": id}}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Deleting Project")


@app.get("/fetchprojects")
def fetch_projects(req: Request, q: str, page: int = 1, per_page: int = 10):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    query = {"user_id": {"$ne": ObjectId(fetch_user['_id'])}}

    if q:
        query["title"] = {"$regex": q, "$options": "i"}
    fetch_projects = db["projects"].find(query).sort(
        "created_at", -1).skip((page-1)*per_page).limit(per_page)
    fetch_count = db["projects"].count_documents(query)
    if not fetch_projects:
        raise HTTPException(status_code=404, detail="No Projects Found")
    result = []
    for i in list(fetch_projects):
        i['_id'] = str(i['_id'])
        fetch_user_id = fetch_user['_id']
        if fetch_user_id:
            i['user_id'] = str(i['user_id'])
        count_interested = db['projects'].count_documents(
            {"_id": ObjectId(i['_id']), "interested_users": ObjectId(fetch_user_id)})
        if count_interested:
            i['is_user_interested'] = True
        else:
            i['is_user_interested'] = False
        if i.get("interested_users"):
            i.pop("interested_users")
        result.append(i)

    return {'meta': {'total_records': fetch_count, 'page': page, 'per_page': per_page}, 'data': result}


@app.get("/fetchuserprojects")
def fetch_projects(req: Request, page: int = 1, per_page: int = 10):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_user_id = fetch_user.get("_id", None)
    fetch_projects = db["projects"].find({"user_id": ObjectId(fetch_user_id)}).sort(
        "created_at", -1).skip((page-1)*per_page).limit(per_page)
    fetch_count = db["projects"].count_documents({})
    if not fetch_projects:
        raise HTTPException(status_code=404, detail="No Projects Found")
    result = []
    for i in list(fetch_projects):
        i['_id'] = str(i['_id'])
        fetch_user_id = i.get("user_id", None)
        if fetch_user_id:
            i['user_id'] = str(i['user_id'])
        count_interested = db['projects'].count_documents(
            {"_id": ObjectId(i['_id']), "interested_users": ObjectId(fetch_user_id)})
        if count_interested:
            i['is_user_interested'] = True
        else:
            i['is_user_interested'] = False
        if i.get("interested_users"):
            i.pop("interested_users")
        result.append(i)
        
    return {'meta': {'total_records': fetch_count, 'page': page, 'per_page': per_page}, 'data': result}


@app.get("/project/{id}")
def fetch_project(req: Request, id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid Project Id")
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_project = db["projects"].find_one({"_id": ObjectId(id)})
    if not fetch_project:
        raise HTTPException(status_code=404, detail="No Project Found")
    fetch_project['_id'] = str(fetch_project['_id'])
    fetch_project['user_id'] = str(fetch_project['user_id'])
    if ObjectId(fetch_project['user_id']) == ObjectId(fetch_user['_id']):
        fetch_project['is_owner'] = True
    else:
        fetch_project['is_owner'] = False
    fetch_interested_users = fetch_project['interested_users']
    interseted_users = []
    is_user_interested = False

    if fetch_interested_users:
        for i in fetch_interested_users:
            user_id = fetch_user.get("_id", None)
            if ObjectId(user_id) == ObjectId(i):
                is_user_interested = True
            fetch_user_details = check_user_exist_using_id(i)
            if fetch_user_details:
                fetch_user_details['_id'] = str(fetch_user_details['_id'])
                interseted_users.append(fetch_user_details)
    fetch_handler = db['users'].find_one(
        {"_id": ObjectId(fetch_project['user_id'])})

    fetch_project['g_id'] = fetch_handler.get("g_id", None)
    fetch_project['interested_users'] = interseted_users
    fetch_project['is_user_interested'] = is_user_interested
    res = {}
    res['meta'] = {'project_id': id}
    res['data'] = fetch_project
    return res


"""
------------------------------------------------------------------------
Notification Section
------------------------------------------------------------------------
"""


@app.get('/notifications')
def get_notifications(req: Request, page: int = 1, per_page: int = 10):
    # print(req.headers.get("Authorization"))
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)

    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    user_id = fetch_user.get("_id", None)
    print(user_id)
    fetch_notifications = db["notifications"].find({"user_id": ObjectId(user_id)}).sort(
        "created_at", -1).skip((page-1)*per_page).limit(per_page)
    fetch_count = db["notifications"].count_documents({"user_id": user_id})
    if not fetch_notifications:
        raise HTTPException(status_code=404, detail="No Notifications Found")
    result = {'new': [], 'read': []}
    db["notifications"].update_many({"user_id": ObjectId(user_id)}, {
                                    "$set": {"is_read": True}})
    for i in list(fetch_notifications):
        i['_id'] = str(i['_id'])
        i['user_id'] = str(i['user_id'])
        created_at = i.pop("created_at")
        i['date'] = created_at.strftime("%d %b %Y")
        i['time'] = created_at.strftime("%I:%M %p")
        if i['is_read'] == False:
            result['new'].append(i)

        else:
            result['read'].append(i)
    return {'meta': {'total_records': fetch_count, 'page': page, 'per_page': per_page}, 'data': result}


@app.get('/isNewnotification')
def is_new_notification(req: Request):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)

    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    user_id = fetch_user.get("_id", None)
    fetch_notifications = db["notifications"].find_one(
        {"user_id": ObjectId(user_id), "is_read": False})
    if not fetch_notifications:
        return {"data": False}
    return {"data": True}


"""
------------------------------------------------------------------------
Favourites Section
------------------------------------------------------------------------
"""


@app.post("/addfavourite")
async def add_favourite(req: Request):
    user = None
    authorization = req.headers.get("Authorization")
    try:
        id_token = authorization.split(" ")[1]
        # print(auth_token)
        # user = id_token.verify_oauth2_token(auth_token,requests.Request(),  '712712296189-2oahq4t0sis03q14jqoccs8e6tuvpbfd.apps.googleusercontent.com', clock_skew_in_seconds=10)
        user = admin_auth.verify_id_token(id_token)

        # print("---------------------------------------")
        # print("USER : ", user)
        # print("---------------------------------------")
    except Exception as e:
        print(e)

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    result = {}
    data = await req.body()
    if data:
        data = json.loads(data)
    result['user_id'] = fetch_user.get("_id", None)
    result['hackathon_id'] = data.get("hackathon_id", None)
    result['project_id'] = data.get("project_id", None)
    if result['hackathon_id']:
        result['hackathon_details'] = {
            "name": data.get("name", None),
            "image": data.get("image", None),
            "heroImage": data.get("heroImage", None),
            "website": data.get("website", None),
            "url": data.get("url", None),
            "location": data.get("location", None),
            "start": data.get("start", None),
            "end": data.get("end", None),
            "mode": data.get("mode", None)
        }
    try:
        collection = db["favourites"]
        fetch_inserted_project = collection.insert_one(result)
        fid = str(fetch_inserted_project.inserted_id)
        result.pop("_id")
        result.pop("user_id")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Adding Favourite")
    if result['project_id']:
        try:
            db['projects'].update_one({"_id": ObjectId(result['project_id'])}, {
                                      "$push": {"interested_users": ObjectId(fetch_user.get("_id"))}})
        except Exception as e:
            print("Error", e)
            raise HTTPException(
                status_code=500, detail="Error Updating Project")
        try:

            fetch_project = db["projects"].find_one(
                {"_id": ObjectId(result['project_id'])})
            fetch_project_handler_id = fetch_project.get("user_id", None)
            if fetch_project_handler_id:

                person_interested = fetch_user.get("name", None)
                title = fetch_project.get("title", None)
                description = person_interested + " has interested in your project " + title
                create_notification(
                    fetch_project_handler_id, 'Your Project Got Some Interests', description, 'Interest')
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=500, detail="Error Creating Notification")
    return {"meta": {"inserted_id": fid}, "data": result}


@app.delete('/deleteFavourite/{id}')
def delete_favourite(req: Request, id: str, is_project: bool = False):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    query = {}
    query['user_id'] = fetch_user.get("_id", None)
    if is_project:
        query['project_id'] = id
    else:
        query['hackathon_id'] = id
    try:
        collection = db["favourites"]
        collection.delete_one(query)
        if is_project:
            db["projects"].update_one({"_id": ObjectId(id)}, {
                                      "$pull": {"interested_users": fetch_user.get("_id", None)}})
        return {"meta": {"status": "success"}, "data": {}}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Adding Favourite")


@app.get("/fetchuserhackathons")
def fetch_favourite_hackathons(req: Request, page: int = 1, per_page: int = 10):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    fetch_user_id = fetch_user.get("_id", None)
    fetch_hackathons = db["favourites"].find({"user_id": ObjectId(fetch_user_id), "project_id": None, "hackathon_details": {
                                             "$exists": True}}).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
    fetch_count = db["favourites"].count_documents({"user_id": ObjectId(
        fetch_user_id), "project_id": None, "hackathon_details": {"$exists": True}})
    if not fetch_hackathons:
        raise HTTPException(status_code=404, detail="No Hackathons Found")
    result = []
    for i in list(fetch_hackathons):
        i['_id'] = str(i['_id'])
        i['hackathon_id'] = str(i['hackathon_id'])
        i['user_id'] = str(i['user_id'])
        result.append(i)
    return {'meta': {'total_records': fetch_count, 'page': page, 'per_page': per_page}, 'data': result}


"""
------------------------------------------------------------------------
Profile Page
------------------------------------------------------------------------
"""


@app.get('/fetchuserprofile')
def fetchuserdetails(req: Request):
    user = asyncio.run(verify(req.headers.get("Authorization")))

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    del fetch_user['_id']
    del fetch_user['g_id']

    return fetch_user


@app.get('/fetchuserpic')
def fetchuserpic(req: Request):
    user = asyncio.run(verify(req.headers.get("Authorization")))

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")

    return {"photo": fetch_user["photo"]}


@app.put('/updateuserpic')
async def updateuserpic(req: Request):
    user = None
    authorization = req.headers.get("Authorization")
    try:
        id_token = authorization.split(" ")[1]
        # print(auth_token)
        # user = id_token.verify_oauth2_token(auth_token,requests.Request(),  '712712296189-2oahq4t0sis03q14jqoccs8e6tuvpbfd.apps.googleusercontent.com', clock_skew_in_seconds=10)
        user = admin_auth.verify_id_token(id_token)

        # print("---------------------------------------")
        # print("USER : ", user)
        # print("---------------------------------------")
    except Exception as e:
        print(e)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")

    userId = fetch_user['_id']
    data = await req.body()
    data = json.loads(data)

    try:
        if data:
            db["users"].update_one({"_id": ObjectId(userId)}, {"$set": data})
        return {"meta": {"status": True}}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Updating Profile")


@app.put('/updateuserprofile')
async def updateuserpic(req: Request):
    user = None
    authorization = req.headers.get("Authorization")
    try:
        id_token = authorization.split(" ")[1]
        # print(auth_token)
        # user = id_token.verify_oauth2_token(auth_token,requests.Request(),  '712712296189-2oahq4t0sis03q14jqoccs8e6tuvpbfd.apps.googleusercontent.com', clock_skew_in_seconds=10)
        user = admin_auth.verify_id_token(id_token)

        # print("---------------------------------------")
        # print("USER : ", user)
        # print("---------------------------------------")
    except Exception as e:
        print(e)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_email = user.get("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="User Email Not Found")
    fetch_user = check_user_exists_using_email(user_email)
    if not fetch_user:
        raise HTTPException(status_code=400, detail="User Not Found")
    userId = fetch_user['_id']
    data = await req.body()
    data = json.loads(data)
    fetch_skills = data.get("skills", None)
    try:
        for skill in fetch_skills:
            count = db["skills"].count_documents({"name": skill})
            if count == 0:
                db["skills"].insert_one({"name": skill, 'subskills': []})
    except:
        pass
    try:
        if data:
            db["users"].update_one({"_id": ObjectId(userId)}, {"$set": data})
        return {"meta": {"status": True}}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error Updating Profile")


# FETCH
# fetch
@app.get('/search')
def findkey(req: Request, q: str, page: int = 1, per_page: int = 10, sort: str = "name", order: str = "asc",batch: int = 1):
    user = asyncio.run(verify(req.headers.get("Authorization")))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    res = {}
    res["meta"] = {}
    res["data"] = []
    order = -1 if order == "desc" else 1
    query1  = {"name": {"$regex": q, "$options": "i"}} 

    fetch_related_skills = db['skills'].find_one(query1)
    if fetch_related_skills:
        main_skill = fetch_related_skills["name"]
        # print(main_skill)
        sub_skills = fetch_related_skills["subskills"]
        # print(sub_skills)
        regex_sub_skills = "|".join(sub_skills)
        # print(regex_sub_skills)
        query2 = {"$or": [{"skills": {"$regex": main_skill, "$options": "i"}}, {"skills": {"$regex": regex_sub_skills, "$options": "i"}}]}
        query3 = {"skills": {"$regex": main_skill, "$options": "i"}}
        if batch != 1:
            batch = str(batch)
            query2 = {"$and": [{"$or": [{"skills": {"$regex": main_skill, "$options": "i"}}, {"skills": {"$regex": regex_sub_skills, "$options": "i"}}]}, {"batch": batch}]}
            query3 = {"$and": [{"skills": {"$regex": main_skill, "$options": "i"}}, {"batch": batch}]}
        if sub_skills:
            regex_sub_skills = "|".join(sub_skills)
            fetch_profiles = db['users'].find(query2).sort(sort, order).skip((page - 1) * per_page).limit(per_page)
            count = db['users'].count_documents(query2)
        else:
            fetch_profiles = db['users'].find(query3).sort(sort, order).skip((page - 1) * per_page).limit(per_page)
            count = db['users'].count_documents(query3)
        for i in list(fetch_profiles):
            i["_id"] = str(i["_id"])
            res["data"].append(i)
        res["meta"] = {"count": count}
    else:
        
        query4 = {"$or": [{"name": {"$regex": q, "$options": "i"}},{"skills": {"$regex": q, "$options": "i"}}]}
        if batch != 1:
            batch = str(batch)
            query4 = {"$and": [{"$or": [{"name": {"$regex": q, "$options": "i"}},{"skills": {"$regex": q, "$options": "i"}}]}, {"batch": batch}]}
        count = db['users'].count_documents(query4)
        fetch_query = db['users'].find(query4).sort(sort, order).skip((page-1)*per_page).limit(per_page)
        for i in list(fetch_query):
            i["_id"] = str(i["_id"])
            res["data"].append(i)
        # print(len(res["data"]))
        res["meta"] = {"count": count}
    return res


app.include_router(auth.router)


# CHAT PAGE INFINITE SCROLL
@app.get('/users/data')
def getUserDataForChat(req: Request, skip=0):
    count = db.users.count_documents({})
    print(count)
    # if (skip+10) > count:
    #   return {'error': 'lomit excedeed'}

    data = db.users.find().skip(int(skip)).limit(10)
    docs = list()

    for doc in list(data):
        if 'g_id' not in doc:
            pass
        else:
            print(doc['g_id'])
            cur_doc = {}
            cur_doc['name'] = doc['name']
            cur_doc['g_id'] = doc['g_id']
            cur_doc['photo'] = doc['photo']
            docs.append(cur_doc)

    return {"data": docs}


@app.get("/")
def home():
    return {"Let's": "Go"}
