import os
import errno
import time
import configparser
import json
import re
import requests
import twitter  # python-twitter

currentPath = os.path.dirname(os.path.realpath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(currentPath, "twitter_lists.ini"))
config.sections()

screen_name = config["DEFAULT"]["screen_name"]
api = twitter.Api(
    consumer_key=config["DEFAULT"]["consumer_key"],
    consumer_secret=config["DEFAULT"]["consumer_secret"],
    access_token_key=config["DEFAULT"]["access_token_key"],
    access_token_secret=config["DEFAULT"]["access_token_secret"],
    sleep_on_rate_limit=True,
    tweet_mode="extended",
)


def getLastId():
    config.read(os.path.join(currentPath, "twitter_lists.ini"))
    config.sections()
    return config["DEFAULT"]["last_id"]


def getFavorites():
    # user_id (int) id of user
    # since_id (int) returns tweets more recent than this id
    # max_id (int) returns tweets older than this id
    # count (int) max 200

    timeline = new_timeline = api.GetFavorites(
        screen_name=screen_name, count=200, include_entities=False, return_json=True,
    )
    tweet_count = len(timeline)
    total = tweet_count
    max_id = timeline[tweet_count - 1]["id"]
    while tweet_count > 1:
        new_timeline = api.GetFavorites(
            screen_name=screen_name,
            count=200,
            max_id=max_id,
            include_entities=False,
            return_json=True,
        )
        tweet_count = len(new_timeline)
        total += tweet_count
        max_id = new_timeline[tweet_count - 1]["id"]
        timeline += new_timeline
    return timeline


def getTweetData(tweet):
    info = {
        "id_str": tweet["id_str"],
        "created_at": tweet["created_at"],
        "screen_name": tweet["user"]["screen_name"],
        "tweet": tweet["full_text"],
        "media": [],
    }
    if (  # may be redundant, not sure if extended_identities can exist without media
        "media" in tweet["extended_entities"]
    ):
        for media in tweet["extended_entities"]["media"]:
            media_type = media["type"]
            if media_type == "video":
                sorted_variants = sorted(  # sort by bitrate, 0 index will typically be m3u8, 1 is the highest bitrate
                    media["video_info"]["variants"],
                    key=lambda i: ("bitrate" not in i, i.get("bitrate", None)),
                    reverse=True,
                )
                index = 0
                if "bitrate" not in sorted_variants[index]:
                    index += 1
                info["media"].append(
                    {
                        "id_str": media["id_str"],
                        "url": sorted_variants[index]["url"],
                        "type": media_type,
                    }
                )
            elif media_type == "photo":
                info["media"].append(
                    {
                        "id_str": media["id_str"],
                        "url": media["media_url_https"],
                        "type": media_type,
                    }
                )

    return info


def downloadMedia(id, media_type, name, url):
    r = requests.get(url, stream=True)
    ext = ".mp4"
    if media_type == "photo":
        ext = ".jpg"
    if r.status_code != 200:
        print(str(r.status_code) + " error downloading tweet with id: " + id)
    else:
        try:
            os.mkdir(os.path.join("downloads", screen_name))
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            pass
        with open(
            os.path.join(currentPath, "downloads", screen_name, name + ext), "wb"
        ) as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)


def updateArchive(archive):
    with open(
        os.path.join(currentPath, "archives", screen_name + ".json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(archive, f, ensure_ascii=False, indent=4)


def loadArchive():
    for i in range(5):
        try:
            with open(
                os.path.join(currentPath, "archives", screen_name + ".json"),
                "r",
                encoding="utf-8",
            ) as f:
                archive = json.load(f)
        except FileNotFoundError:
            with open(
                os.path.join(currentPath, "archives", screen_name + ".json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(dict(), f, ensure_ascii=False, indent=4)
            continue
        break
    return archive


def main():
    timeline = getFavorites()
    archive = loadArchive()
    favorites = []
    for idx, tweet in enumerate(timeline):
        if "extended_entities" in tweet:
            id = tweet["id_str"]
            if id in archive:
                continue
            if id not in archive:
                archive[id] = None
                favorites.append(getTweetData(tweet))
    print(str(len(favorites)) + " new images/videos")
    for tweet in favorites:
        tweet_id = tweet["id_str"]
        date = (
            "["
            + time.strftime(
                "%Y-%m-%d",
                time.strptime(tweet["created_at"], "%a %b %d %H:%M:%S +0000 %Y"),
            )
            + "] "
        )
        for idx, media in enumerate(tweet["media"]):
            filename = re.sub("[^\\w0-9 ]", " ", tweet["tweet"]) + "\n"
            filename = re.sub("http.+[\\s|\n]", "", filename)
            filename = re.sub(" +", " ", filename)
            filename = filename[  # cut the tweet length because of long path errors in windows
                :140
            ]
            # filename = tweet_id #UNCOMMENT THIS LINE FOR TWEET ID AS FILENAME
            filename = date + filename + " - " + str(idx)
            downloadMedia(
                tweet_id, media["type"], filename, media["url"],
            )
    updateArchive(archive)


main()

