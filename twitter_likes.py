import argparse
import configparser
import twitter
import os
import json
from likes import Likes
import sys


class Downloader:
    def __init__(self):
        self._current_path = os.path.dirname(os.path.realpath(__file__))

    def downloadLikes(self, api, screen_name, force_redownload):
        liked_tweets = Likes(api, screen_name, self._current_path, force_redownload)
        liked_tweets.download()

    def generateConfig(self):
        base = {
            "consumer_key": "",
            "consumer_secret": "",
            "access_token_key": "",
            "access_token_secret": "",
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=4)
        print("Config generated at config.json")
        sys.exit()

    def main(self):
        parser = argparse.ArgumentParser(
            description="Download media from liked tweets of a specified user."
        )

        parser.add_argument(
            "-u", "--user", help="Twitter username, @twitter would just be twitter"
        )
        parser.add_argument(
            "--images",
            help="Download only images, downloads videos and images by default",
            action="store_true",
        )
        parser.add_argument(
            "--videos",
            help="Download only videos, downloads videos and images by default",
            action="store_true",
        )
        parser.add_argument(
            "-g",
            "--generate-config",
            help="Generates skeleton config file(config.json), will overwrite existing config if exists",
            action="store_true",
        )
        parser.add_argument(
            "-c",
            "--config",
            help="JSON file containing API keys. Default(config.json) is used if not specified",
        )
        parser.add_argument(
            "-f", "--force", help="Redownloads all media", action="store_true"
        )

        args = parser.parse_args()

        if args.generate_config:
            self.generateConfig()
        if not args.user:
            print("No user specified, exiting")
            sys.exit()

        config_name = "config.json"

        if args.config:
            config_name = args.config

        try:
            with open(config_name, "r", encoding="utf-8") as f:
                config = json.load(f)
            api = twitter.Api(
                consumer_key=config["consumer_key"],
                consumer_secret=config["consumer_secret"],
                access_token_key=config["access_token_key"],
                access_token_secret=config["access_token_secret"],
                sleep_on_rate_limit=True,
                tweet_mode="extended",
            )
        except FileNotFoundError:
            raise
        except json.decoder.JSONDecodeError:
            raise

        self.downloadLikes(api, args.user, args.force)


downloader = Downloader()
downloader.main()

