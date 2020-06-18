import os
import sys
import errno
import json
import requests
import time
import re


class Likes:
    def __init__(self, api, screen_name, current_path, force_redownload):
        self._api = api
        self._screen_name = screen_name
        self._current_path = current_path
        self._force_redownload = force_redownload
        self._archives_path = os.path.join(current_path, "archives")
        self._downloads_path = os.path.join(current_path, "downloads", screen_name)

    def loadArchive(self):
        """
            Loads archive json file for a specific twitter account
            Keys are the tweet id's that have been downloaded, values are None
            Checks for JSONDecodeError which may happen if user messes up formatting of archive file
                Gives the user the option to reset the archive and download all media again
            Checks if the file exists, if it doesn't then it loads an empty dict
        """
        try:
            with open(
                os.path.join(self._archives_path, self._screen_name + ".json"),
                "r",
                encoding="utf-8",
            ) as f:
                archive = json.load(f)
        except json.decoder.JSONDecodeError:
            print(
                "There was a problem with the archive file. Proceed to clear archive and redownload all media or exit."
            )
            user_input = None
            while user_input != "n" and user_input != "y":
                user_input = str(input("Proceed (y/n)?: ")).lower()
            if user_input == "n":
                print("exiting")
                sys.exit()
            archive = dict()
        except FileNotFoundError:
            archive = dict()
        return archive

    def getFavorites(self, max_id):
        return self._api.GetFavorites(
            screen_name=self._screen_name,
            count=200,
            max_id=max_id,
            include_entities=False,
            return_json=True,
        )

    def getAllFavorites(self):
        """
            Retrieves all liked tweets on an account 200 at a time 
            (75 requests/15min = 15000 liked tweets/15min max)
        """
        timeline = []
        tweet_count = 2
        total = 0
        max_id = 0
        while tweet_count > 1:
            new_timeline = self.getFavorites(max_id)
            tweet_count = len(new_timeline)
            if tweet_count > 1:
                total += tweet_count
                max_id = new_timeline[tweet_count - 1]["id"]
                new_timeline.reverse()
                timeline = new_timeline + timeline
        print("found " + str(total) + " liked tweets")
        return timeline

    def getTweetData(self, tweet):
        """
            Stores some metadata about the tweet that can be used later, maybe to create some sort of gui to view tweets
            Stores direct links to all the media for a tweet
        """
        info = {
            "id_str": tweet["id_str"],
            "created_at": tweet["created_at"],
            "screen_name": tweet["user"]["screen_name"],
            "tweet": tweet["full_text"],
            "media": [],
        }
        if "extended_entities" in tweet and "media" in tweet["extended_entities"]:
            for media in tweet["extended_entities"]["media"]:
                media_type = media["type"]
                if media_type == "video" or media_type == "animated_gif":
                    sorted_variants = sorted(  # sort by bitrate, 0 index will typically be m3u8, 1 is the highest bitrate
                        media["video_info"]["variants"],
                        key=lambda i: ("bitrate" not in i, i.get("bitrate", None)),
                        reverse=True,
                    )
                    index = 0
                    # videos have m3u8 variant with no bitrate key, highest bit rate ends up being index 1
                    # gifs have only 1 variant with a bitrate
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
                            "url": media["media_url_https"] + ":large",
                            "type": media_type,
                        }
                    )
        return info

    def downloadMedia(self, id, filename, url):
        """
            Downloads media specified at url
            Files are downloaded to a folder with the name "screen_name" in the downloads folder
        """
        r = requests.get(url, stream=True)
        if r.status_code != 200:
            print(str(r.status_code) + " error downloading tweet with id: " + id)
        else:
            try:
                os.makedirs(os.path.join("downloads", self._screen_name))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                pass
            file_path = os.path.join(self._downloads_path, filename)
            if os.path.exists(file_path) == False:
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024 * 10):
                        if chunk:
                            f.write(chunk)
            else:
                print("tweet with id " + id + " already exists, skipping download")

    def updateArchive(self, archive):
        """
            Update archive file for user with new liked tweets
        """
        while True:
            try:
                with open(
                    os.path.join(self._archives_path, self._screen_name + ".json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(archive, f, ensure_ascii=False, indent=4)
                break
            except FileNotFoundError:
                try:
                    os.makedirs(self._archives_path)
                    continue
                except FileExistsError:
                    pass

    def writeTimeline(self, timeline):
        # Writes new liked tweets to timeline.json with all data from api
        try:
            with open(
                os.path.join(self._downloads_path, "timeline.json"),
                "r",
                encoding="utf-8",
            ) as f:
                old_timeline = json.load(f)
        except FileNotFoundError:
            old_timeline = []
        while True:
            try:
                with open(
                    os.path.join(self._downloads_path, "timeline.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(old_timeline + timeline, f, ensure_ascii=False, indent=4)
                break
            except FileNotFoundError:
                os.makedirs(self._downloads_path)
                continue

    def writeFavorites(self, favorites):
        "Adds new liked tweets to favorites.json with a lot less data"
        try:
            with open(
                os.path.join(self._downloads_path, "favorites.json"),
                "r",
                encoding="utf-8",
            ) as f:
                old_favorites = json.load(f)
        except FileNotFoundError:
            old_favorites = []

        with open(
            os.path.join(self._downloads_path, "favorites.json"), "w", encoding="utf-8",
        ) as f:
            json.dump(old_favorites + favorites, f, ensure_ascii=False, indent=4)

    def writeTweetData(self, timeline, favorites):
        self.writeTimeline(timeline)
        self.writeFavorites(favorites)

    def reset(self):
        with open(
            os.path.join(self._archives_path, self._screen_name + ".json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(dict(), f, ensure_ascii=False, indent=4)
        while True:
            try:
                with open(
                    os.path.join(self._downloads_path, "favorites.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
                break
            except FileNotFoundError:
                os.makedirs(self._downloads_path)

    def getFilename(self, date, tweet, idx, id, media_type):
        tweet_id = tweet["id_str"]
        ext = ".mp4"
        if media_type == "photo":
            ext = ".jpg"
        if not id:
            # filename = re.sub("[^\\w# :\/\.]", " ", tweet["tweet"])
            tweet_text = re.sub(r'[\\*?"<>|~]', " ", tweet["tweet"])
            tweet_text = re.sub(r"https?\S+", "", tweet_text)
            # filename = re.sub("[^\\w#]", " ", filename)
            tweet_text = re.sub(r"\n|:|/", " ", tweet_text).strip()
            tweet_text = re.sub(r" +", " ", tweet_text)
            tweet_text_length = 250 - (
                len(date + " - " + tweet_id + " - " + str(idx)) + 4
            )
            filename = (
                date
                + tweet_text[  # cut the tweet length because of long path errors in windows
                    :tweet_text_length
                ]
                + " - "
                + tweet_id
                + " - "
                + str(idx)
                + ext
            )
            return filename

        return tweet_id

    def download(self):
        if self._force_redownload:
            self.reset()
        archive = self.loadArchive()
        timeline = self.getAllFavorites()
        new_tweets = []
        favorites = []

        for idx, tweet in enumerate(timeline):
            id = tweet["id_str"]
            if id in archive:
                continue
            else:
                archive[id] = None
                new_tweets.append(tweet)
                favorites.append(self.getTweetData(tweet))

        print(str(len(favorites)) + " new favorites with images/videos")

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
                filename = self.getFilename(date, tweet, idx, False, media["type"])
                media["filename"] = filename
                self.downloadMedia(
                    tweet_id, filename, media["url"],
                )
        self.writeTweetData(new_tweets, favorites)
        self.updateArchive(archive)
        print("done")
