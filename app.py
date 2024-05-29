import os
import aiohttp
import getpass
import json
import hashlib
from Crypto.Cipher import DES
import base64
from bs4 import BeautifulSoup
import time
import asyncio
import re
import subprocess
from faster_whisper import WhisperModel

os.environ['KMP_DUPLICATE_LIB_OK']='True'
url = "https://i-learning.cycu.edu.tw/"

# MD5 Encrypt
def md5_encode(input_string) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input_string.encode('utf-8'))
    return md5_hash.hexdigest()

# DES Encrypt ECB NoPadding
def des_encode(key:str, data) -> str:
    cipher = DES.new(key.encode('utf-8'), DES.MODE_ECB)
    encrypted_data = cipher.encrypt(data.encode('utf-8'))
    return str(base64.encodebytes(encrypted_data),encoding='utf-8').replace("\n","")

async def fetch_login_key(session):
    while True:
        async with session.get(url + "sys/door/re_gen_loginkey.php?xajax=reGenLoginKey", headers=headers) as response:
            res = await response.text()
            if "loginForm.login_key.value = \"" in res:
                return res.split("loginForm.login_key.value = \"")[1].split("\"")[0]

async def login(session, id, pwd, loginKey) -> bool:
    async with session.post(url + "login.php", headers=headers, data={
        "username": id,
        "pwd": pwd,
        "password": "*" * len(pwd),
        "login_key": loginKey,
        "encrypt_pwd": des_encode(md5_encode(pwd)[:4] + loginKey[:4], pwd + " " * (16 - len(pwd) % 16) if len(pwd) % 16 != 0 else pwd),
    }) as response:
        res = await response.text()
        if "lang=\"big5" in res:
            print("登入失敗，請重新再試!")
            return False
    return True

async def fetch_courses(session):
    async with session.get(url + "learn/mooc_sysbar.php", headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        courses = {
            option["value"]: option.text
            for child in soup.select("optgroup[label=\"正式生、旁聽生\"]")
            for option in child.find_all("option")
        }
        return courses

async def fetch_videos(session, course_id) -> dict:
    async with session.get(url + f"xmlapi/index.php?action=my-course-path-info&cid={course_id}", headers=headers) as response:
        items = json.loads(await response.text())
        hrefs = dict()
        if items['code'] == 0:
            def search_hrefs(data):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key == 'href' and value.endswith('.mp4'):
                            pattern = r'[<>:"/\\|?*\x00-\x1F\x7F]'
                            name = re.sub(pattern,'',str(data['text']))
                            hrefs[name] = str(value)
                        elif isinstance(value, (dict, list)):
                            search_hrefs(value)
                elif isinstance(data, list):
                    for item in data:
                        search_hrefs(item)
            search_hrefs(items['data']['path']['item'])
        return hrefs

async def downloadVideo(session, filename, href) -> str:
    async with session.get(href, headers=headers) as response:
        if response.status != 200: 
            return
        # Retrieve file name
        filename += ".mp4"
        save_path = f"videos/"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        file_path = os.path.join(save_path, filename)
        if os.path.exists(file_path):
            return file_path
        # Write mp4
        with open(file_path, 'wb') as file:
            async for chunk in response.content.iter_chunked(8192):
                if chunk:
                    file.write(chunk)
        return file_path

async def transcribe(model, videoPath, name):
    # file = open(videoPath, "rb")
    # model = whisper.load_model(modelName,device=device,download_root=download_root)

    audioFile = extractAudio(videoPath)
    # result = model.transcribe(audioFile)
    segments, _ = model.transcribe(audioFile, language="zh")
    save_path = f"videos/"
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    file_path = os.path.join(save_path, name +"_transcrption.txt")
    with open(file_path, 'w', encoding="utf-8") as txt:
        for segment in segments:
            txt.write("[%.2fs -> %.2fs] %s\n" % (segment.start, segment.end, segment.text))
        # for segment in result['segments']:
            # txt.write("[%.2fs -> %.2fs] %s\n" % (segment["start"], segment["end"], segment["text"]))
    os.remove(audioFile)
            
def extractAudio(video_file, output_ext="mp3"):
    filename, _ = os.path.splitext(video_file)
    subprocess.call(["ffmpeg", "-y", "-i", video_file, f"{filename}.{output_ext}"], 
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT)
    return f"{filename}.{output_ext}"
    

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15"}

async def main():
    os.system("title CYCU-iLearning-Video-Transcription")
    print("<!!! 尊重版權/著作權 尊重版權/著作權 尊重版權/著作權 !!!>")
    id = input("輸入您的學號：")
    pwd = getpass.getpass("輸入您的itouch密碼：")
    
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        login_key = await fetch_login_key(session)
        if not await login(session, id, pwd, login_key):
            return await main()

        print("0: CPU")
        print("1: CUDA (GPU)")
        print("選擇運算方式")
        device = "cpu" if int(input("> ")) == 0 else "cuda"
        
        print("0: small 能力中等")
        print("1: medium 能力弱")
        print("2: large-v3 能力強")
        print("選擇模型類型")
        modelChoice= ['small','medium','large-v3']
        modelName = modelChoice[int(input("> "))]
        
        download_root = "model/"
        if not os.path.exists(download_root):
            os.makedirs(download_root)
        model = WhisperModel(modelName, device=device,download_root=download_root , compute_type="auto")
        
        courses = await fetch_courses(session)
        try:
            while(True):
                i = 0
                courseKeys = list(courses.keys())
                for i in range(len(courseKeys)):
                    print( str(i) + ": "+ courses[courseKeys[i]])
                    i +=1
                
                print("輸入編號選擇課程")
                
                keyIndex = None
                while(keyIndex == None or keyIndex >= len(courseKeys) or keyIndex < -1):
                    try:
                        keyIndex = int(input("> "))
                    except Exception as e:
                        print(e)
                        continue
                if keyIndex == -1:
                    continue
                
                hrefs = await fetch_videos(session, courseKeys[keyIndex])
                
                if len(hrefs) == 0:
                    continue
                
                for i, (name, _) in enumerate(hrefs.items()):
                    print(str(i) + ": " + name)
                
                print("輸入編號轉錄影片 (輸入 -1 返回)")
                courseIndex = None
                while(courseIndex == None or courseIndex >= len(hrefs) or courseIndex < -1):
                    try:
                        courseIndex = int(input("> "))
                    except Exception as e:
                        print(e)
                        continue
                if courseIndex == -1:
                    continue
                
                print("影片下載中...")
                start = time.time()
                videoName = list(hrefs.keys())[courseIndex]
                filePath = await downloadVideo(session, videoName, hrefs[videoName])
                print("下載完成! 耗時: %.2fs" % (time.time() - start))
                
                start = time.time()
                print("AI轉錄中...")
                await transcribe(model, filePath, videoName)
                print("轉錄完成! 耗時: %.2fs" % (time.time() - start))
                
                input("點擊Enter繼續...")
        finally:
            os.system("pause")
        
                    
if __name__ == "__main__":
    asyncio.run(main())