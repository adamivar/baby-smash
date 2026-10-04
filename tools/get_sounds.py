"""Download the real recordings (spoken words + sound effects) and trim/level them for the game.

Re-run any time: already-processed files are skipped. Edit PICKS / WORDS to change one
(delete its .wav first).
Output: ../sounds/<Word>.wav (sound effects, ~1-3 s), ../sounds/words/<Word>.wav (spoken words)
and ../sounds/CREDITS.txt
"""
import array
import math
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import wave

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (BabySmash personal project)"}
WIKI_UA = {"User-Agent": "BabySmashSoundFetcher/1.0 (personal hobby project; python-urllib)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds")
RATE = 44100

BSB = "https://bigsoundbank.com/UPLOAD/mp3/{}.mp3"
CC0 = "BigSoundBank #{} by Joseph Sardin - CC0 (public domain) - https://bigsoundbank.com"
# word: (url, credit, max seconds, extra gain)
PICKS = {
    "Cat": (BSB.format("1898"), CC0.format("1898"), 2.5, 1.0),
    "Dog": (BSB.format("2955"), CC0.format("2955"), 2.5, 1.0),
    "Frog": (BSB.format("0997"), CC0.format("0997"), 2.5, 1.0),
    "Horse": (BSB.format("0863"), CC0.format("0863"), 3.0, 1.0),
    "Owl": (BSB.format("3459"), CC0.format("3459"), 2.5, 1.0),
    "Sheep": (BSB.format("2343"), CC0.format("2343"), 2.0, 1.0),
    "Cow": (BSB.format("2386"), CC0.format("2386"), 3.0, 1.0),
    "Chick": (BSB.format("1908"), CC0.format("1908"), 2.5, 1.0),
    "Bird": (BSB.format("3503"), CC0.format("3503"), 3.0, 1.0),
    "Bee": (BSB.format("1000"), CC0.format("1000"), 2.5, 1.0),
    "Baby": (BSB.format("0232"), CC0.format("0232"), 3.0, 1.0),
    "Train": (BSB.format("3011"), CC0.format("3011"), 3.0, 0.8),
    "Car": (BSB.format("0290"), CC0.format("0290"), 3.0, 0.9),
    "Bus": (BSB.format("1832"), CC0.format("1832"), 2.0, 0.7),
    "Keys": (BSB.format("2425"), CC0.format("2425"), 2.5, 1.0),
    "Ball": (BSB.format("2239"), CC0.format("2239"), 2.5, 1.0),
    "Apple": (BSB.format("1114"), CC0.format("1114"), 2.0, 1.0),
    "Juice": (BSB.format("1244"), CC0.format("1244"), 2.5, 1.0),
    "Milk": (BSB.format("1156"), CC0.format("1156"), 2.5, 1.0),
    "Fish": (BSB.format("0183"), CC0.format("0183"), 2.5, 1.0),
    "Shoe": (BSB.format("0166"), CC0.format("0166"), 2.5, 1.0),
    "Book": (BSB.format("2212"), CC0.format("2212"), 2.0, 1.0),
    "Sun": (BSB.format("1670"), CC0.format("1670"), 3.0, 1.0),
    "Moon": (BSB.format("0425"), CC0.format("0425"), 2.5, 0.6),
    "Giraffe": (BSB.format("0986"), CC0.format("0986"), 2.5, 1.0),
    "Bunny": (BSB.format("2284"), CC0.format("2284"), 2.0, 0.8),
    "Hand": (BSB.format("2363"), CC0.format("2363"), 2.5, 1.0),
    "Mouth": (BSB.format("2200"), CC0.format("2200"), 2.0, 1.0),
    "Tooth": (BSB.format("2190"), CC0.format("2190"), 2.0, 0.9),
    "Nose": (BSB.format("3308"), CC0.format("3308"), 2.5, 0.9),
    "Arm": (BSB.format("1796"), CC0.format("1796"), 2.0, 0.8),
    "Lion": ("https://upload.wikimedia.org/wikipedia/commons/d/d3/Lionroar.wav",
             '"Lionroar.wav" by Jonathan Growcott, Alex Lobora, Andrew Markham, Charlotte E. Searle, '
             "Johan Wahlström, Matthew Wijers, Benno I. Simmons - CC BY 4.0 - "
             "https://commons.wikimedia.org/wiki/File:Lionroar.wav", 3.0, 0.5),
    "Duck": ("https://upload.wikimedia.org/wikipedia/commons/d/d0/Domestic_duck_sound_01.wav",
             '"Domestic duck sound 01.wav" by Ganesh Mohan T - CC BY-SA 4.0 - '
             "https://commons.wikimedia.org/wiki/File:Domestic_duck_sound_01.wav", 2.5, 1.0),
}
# Real people saying the words (Wikimedia Commons: Lingua Libre + Wiktionary).
WORDS = {  # spoken word: (url, credit)
    'Apple': ('https://upload.wikimedia.org/wikipedia/commons/6/61/LL-Q1860_%28eng%29-Grendelkhan-apple.wav',
             'LL-Q1860 (eng)-Grendelkhan-apple.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-apple.wav'),
    'Ball': ('https://upload.wikimedia.org/wikipedia/commons/8/86/LL-Q1860_%28eng%29-Grendelkhan-ball.wav',
             'LL-Q1860 (eng)-Grendelkhan-ball.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-ball.wav'),
    'Cat': ('https://upload.wikimedia.org/wikipedia/commons/7/75/LL-Q1860_%28eng%29-Grendelkhan-cat.wav',
             'LL-Q1860 (eng)-Grendelkhan-cat.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-cat.wav'),
    'Dog': ('https://upload.wikimedia.org/wikipedia/commons/9/9f/LL-Q1860_%28eng%29-Grendelkhan-dog.wav',
             'LL-Q1860 (eng)-Grendelkhan-dog.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-dog.wav'),
    'Elephant': ('https://upload.wikimedia.org/wikipedia/commons/a/ab/LL-Q1860_%28eng%29-Grendelkhan-elephant.wav',
             'LL-Q1860 (eng)-Grendelkhan-elephant.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-elephant.wav'),
    'Horse': ('https://upload.wikimedia.org/wikipedia/commons/8/8a/LL-Q1860_%28eng%29-Grendelkhan-horse.wav',
             'LL-Q1860 (eng)-Grendelkhan-horse.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-horse.wav'),
    'Juice': ('https://upload.wikimedia.org/wikipedia/commons/3/30/LL-Q1860_%28eng%29-Grendelkhan-juice.wav',
             'LL-Q1860 (eng)-Grendelkhan-juice.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-juice.wav'),
    'Keys': ('https://upload.wikimedia.org/wikipedia/commons/8/8a/LL-Q1860_%28eng%29-Grendelkhan-keys.wav',
             'LL-Q1860 (eng)-Grendelkhan-keys.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-keys.wav'),
    'Lion': ('https://upload.wikimedia.org/wikipedia/commons/f/fd/LL-Q1860_%28eng%29-Grendelkhan-lion.wav',
             'LL-Q1860 (eng)-Grendelkhan-lion.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-lion.wav'),
    'Monkey': ('https://upload.wikimedia.org/wikipedia/commons/f/f0/LL-Q1860_%28eng%29-Grendelkhan-monkey.wav',
             'LL-Q1860 (eng)-Grendelkhan-monkey.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-monkey.wav'),
    'Nose': ('https://upload.wikimedia.org/wikipedia/commons/0/0d/LL-Q1860_%28eng%29-Grendelkhan-nose.wav',
             'LL-Q1860 (eng)-Grendelkhan-nose.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-nose.wav'),
    'Pig': ('https://upload.wikimedia.org/wikipedia/commons/2/24/LL-Q1860_%28eng%29-Grendelkhan-pig.wav',
             'LL-Q1860 (eng)-Grendelkhan-pig.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-pig.wav'),
    'Duck': ('https://upload.wikimedia.org/wikipedia/commons/c/cb/LL-Q1860_%28eng%29-Grendelkhan-duck.wav',
             'LL-Q1860 (eng)-Grendelkhan-duck.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-duck.wav'),
    'Bunny': ('https://upload.wikimedia.org/wikipedia/commons/c/c6/LL-Q1860_%28eng%29-Grendelkhan-rabbit.wav',
             'LL-Q1860 (eng)-Grendelkhan-rabbit.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-rabbit.wav'),
    'Sheep': ('https://upload.wikimedia.org/wikipedia/commons/8/87/LL-Q1860_%28eng%29-Grendelkhan-sheep.wav',
             'LL-Q1860 (eng)-Grendelkhan-sheep.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-sheep.wav'),
    'Train': ('https://upload.wikimedia.org/wikipedia/commons/4/46/LL-Q1860_%28eng%29-Grendelkhan-train.wav',
             'LL-Q1860 (eng)-Grendelkhan-train.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-train.wav'),
    'Bus': ('https://upload.wikimedia.org/wikipedia/commons/1/15/LL-Q1860_%28eng%29-Grendelkhan-bus.wav',
             'LL-Q1860 (eng)-Grendelkhan-bus.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-bus.wav'),
    'Car': ('https://upload.wikimedia.org/wikipedia/commons/2/24/LL-Q1860_%28eng%29-Grendelkhan-car.wav',
             'LL-Q1860 (eng)-Grendelkhan-car.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-car.wav'),
    'Fish': ('https://upload.wikimedia.org/wikipedia/commons/0/0a/LL-Q1860_%28eng%29-Grendelkhan-fish.wav',
             'LL-Q1860 (eng)-Grendelkhan-fish.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-fish.wav'),
    'Baby': ('https://upload.wikimedia.org/wikipedia/commons/2/22/LL-Q1860_%28eng%29-Grendelkhan-baby.wav',
             'LL-Q1860 (eng)-Grendelkhan-baby.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-baby.wav'),
    'Bee': ('https://upload.wikimedia.org/wikipedia/commons/0/03/LL-Q1860_%28eng%29-Grendelkhan-bee.wav',
             'LL-Q1860 (eng)-Grendelkhan-bee.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-bee.wav'),
    'Cow': ('https://upload.wikimedia.org/wikipedia/commons/6/62/LL-Q1860_%28eng%29-Grendelkhan-cow.wav',
             'LL-Q1860 (eng)-Grendelkhan-cow.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-cow.wav'),
    'Bird': ('https://upload.wikimedia.org/wikipedia/commons/a/a8/LL-Q1860_%28eng%29-Grendelkhan-bird.wav',
             'LL-Q1860 (eng)-Grendelkhan-bird.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-bird.wav'),
    'Bear': ('https://upload.wikimedia.org/wikipedia/commons/c/c0/LL-Q1860_%28eng%29-Grendelkhan-bear.wav',
             'LL-Q1860 (eng)-Grendelkhan-bear.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-bear.wav'),
    'Chick': ('https://upload.wikimedia.org/wikipedia/commons/7/74/LL-Q1860_%28eng%29-Grendelkhan-chick.wav',
             'LL-Q1860 (eng)-Grendelkhan-chick.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-chick.wav'),
    'Shoe': ('https://upload.wikimedia.org/wikipedia/commons/0/04/LL-Q1860_%28eng%29-Grendelkhan-shoe.wav',
             'LL-Q1860 (eng)-Grendelkhan-shoe.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-shoe.wav'),
    'Milk': ('https://upload.wikimedia.org/wikipedia/commons/2/24/LL-Q1860_%28eng%29-Grendelkhan-milk.wav',
             'LL-Q1860 (eng)-Grendelkhan-milk.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-milk.wav'),
    'Hat': ('https://upload.wikimedia.org/wikipedia/commons/1/12/LL-Q1860_%28eng%29-Grendelkhan-hat.wav',
             'LL-Q1860 (eng)-Grendelkhan-hat.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-hat.wav'),
    'Moon': ('https://upload.wikimedia.org/wikipedia/commons/5/54/LL-Q1860_%28eng%29-Grendelkhan-moon.wav',
             'LL-Q1860 (eng)-Grendelkhan-moon.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-moon.wav'),
    'Sun': ('https://upload.wikimedia.org/wikipedia/commons/3/39/LL-Q1860_%28eng%29-Grendelkhan-sun.wav',
             'LL-Q1860 (eng)-Grendelkhan-sun.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-sun.wav'),
    'Book': ('https://upload.wikimedia.org/wikipedia/commons/4/44/LL-Q1860_%28eng%29-Grendelkhan-book.wav',
             'LL-Q1860 (eng)-Grendelkhan-book.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-book.wav'),
    'hello': ('https://upload.wikimedia.org/wikipedia/commons/e/e0/LL-Q1860_%28eng%29-Grendelkhan-hello.wav',
             'LL-Q1860 (eng)-Grendelkhan-hello.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-hello.wav'),
    'bye': ('https://upload.wikimedia.org/wikipedia/commons/8/84/LL-Q1860_%28eng%29-Grendelkhan-bye.wav',
             'LL-Q1860 (eng)-Grendelkhan-bye.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-bye.wav'),
    'where': ('https://upload.wikimedia.org/wikipedia/commons/6/63/LL-Q1860_%28eng%29-Grendelkhan-where.wav',
             'LL-Q1860 (eng)-Grendelkhan-where.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-where.wav'),
    'Frog': ('https://upload.wikimedia.org/wikipedia/commons/0/0e/En-us-frog.ogg',
             'En-us-frog.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-frog.ogg'),
    'Giraffe': ('https://upload.wikimedia.org/wikipedia/commons/a/a8/En-us-giraffe.ogg',
             'En-us-giraffe.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-giraffe.ogg'),
    'Ice cream': ('https://upload.wikimedia.org/wikipedia/commons/2/28/En-us-ice_cream.ogg',
             'En-us-ice cream.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-ice_cream.ogg'),
    'Owl': ('https://upload.wikimedia.org/wikipedia/commons/7/74/En-us-owl.ogg',
             'En-us-owl.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-owl.ogg'),
    'Banana': ('https://upload.wikimedia.org/wikipedia/commons/6/61/En-us-banana.ogg',
             'En-us-banana.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-banana.ogg'),
    'Eyes': ('https://upload.wikimedia.org/wikipedia/commons/4/49/LL-Q1860_%28eng%29-Grendelkhan-eyes.wav',
             'LL-Q1860 (eng)-Grendelkhan-eyes.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-eyes.wav'),
    'Ear': ('https://upload.wikimedia.org/wikipedia/commons/c/c8/LL-Q1860_%28eng%29-Grendelkhan-ear.wav',
             'LL-Q1860 (eng)-Grendelkhan-ear.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-ear.wav'),
    'Mouth': ('https://upload.wikimedia.org/wikipedia/commons/c/c3/LL-Q1860_%28eng%29-Grendelkhan-mouth.wav',
             'LL-Q1860 (eng)-Grendelkhan-mouth.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-mouth.wav'),
    'Tongue': ('https://upload.wikimedia.org/wikipedia/commons/4/44/LL-Q1860_%28eng%29-Grendelkhan-tongue.wav',
             'LL-Q1860 (eng)-Grendelkhan-tongue.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-tongue.wav'),
    'Tooth': ('https://upload.wikimedia.org/wikipedia/commons/1/1b/LL-Q1860_%28eng%29-Grendelkhan-tooth.wav',
             'LL-Q1860 (eng)-Grendelkhan-tooth.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-tooth.wav'),
    'Hand': ('https://upload.wikimedia.org/wikipedia/commons/e/e2/LL-Q1860_%28eng%29-Grendelkhan-hand.wav',
             'LL-Q1860 (eng)-Grendelkhan-hand.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-hand.wav'),
    'Foot': ('https://upload.wikimedia.org/wikipedia/commons/4/44/LL-Q1860_%28eng%29-Grendelkhan-foot.wav',
             'LL-Q1860 (eng)-Grendelkhan-foot.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-foot.wav'),
    'Leg': ('https://upload.wikimedia.org/wikipedia/commons/1/17/LL-Q1860_%28eng%29-Grendelkhan-leg.wav',
             'LL-Q1860 (eng)-Grendelkhan-leg.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-leg.wav'),
    'Arm': ('https://upload.wikimedia.org/wikipedia/commons/5/5a/LL-Q1860_%28eng%29-Grendelkhan-arm.wav',
             'LL-Q1860 (eng)-Grendelkhan-arm.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-arm.wav'),
    'Number 1': ('https://upload.wikimedia.org/wikipedia/commons/8/83/LL-Q1860_%28eng%29-Grendelkhan-one.wav',
             'LL-Q1860 (eng)-Grendelkhan-one.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-one.wav'),
    'Number 2': ('https://upload.wikimedia.org/wikipedia/commons/f/f6/LL-Q1860_%28eng%29-Grendelkhan-two.wav',
             'LL-Q1860 (eng)-Grendelkhan-two.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-two.wav'),
    'Number 3': ('https://upload.wikimedia.org/wikipedia/commons/a/ad/LL-Q1860_%28eng%29-Grendelkhan-three.wav',
             'LL-Q1860 (eng)-Grendelkhan-three.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-three.wav'),
    'Number 4': ('https://upload.wikimedia.org/wikipedia/commons/e/ea/LL-Q1860_%28eng%29-Grendelkhan-four.wav',
             'LL-Q1860 (eng)-Grendelkhan-four.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-four.wav'),
    'Number 5': ('https://upload.wikimedia.org/wikipedia/commons/1/16/LL-Q1860_%28eng%29-Grendelkhan-five.wav',
             'LL-Q1860 (eng)-Grendelkhan-five.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-five.wav'),
    'Number 6': ('https://upload.wikimedia.org/wikipedia/commons/a/a1/LL-Q1860_%28eng%29-Grendelkhan-six.wav',
             'LL-Q1860 (eng)-Grendelkhan-six.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-six.wav'),
    'Number 7': ('https://upload.wikimedia.org/wikipedia/commons/2/29/LL-Q1860_%28eng%29-Grendelkhan-seven.wav',
             'LL-Q1860 (eng)-Grendelkhan-seven.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-seven.wav'),
    'Number 8': ('https://upload.wikimedia.org/wikipedia/commons/7/7a/LL-Q1860_%28eng%29-Grendelkhan-eight.wav',
             'LL-Q1860 (eng)-Grendelkhan-eight.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-eight.wav'),
    'Number 9': ('https://upload.wikimedia.org/wikipedia/commons/9/9a/LL-Q1860_%28eng%29-Grendelkhan-nine.wav',
             'LL-Q1860 (eng)-Grendelkhan-nine.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-nine.wav'),
    'Number 10': ('https://upload.wikimedia.org/wikipedia/commons/c/c4/LL-Q1860_%28eng%29-Grendelkhan-ten.wav',
             'LL-Q1860 (eng)-Grendelkhan-ten.wav by Grendelkhan - CC0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Grendelkhan-ten.wav'),
    'Letter A': ('https://upload.wikimedia.org/wikipedia/commons/4/42/En-us-A.ogg',
             'En-us-A.ogg by unknown speaker - Public domain - https://commons.wikimedia.org/wiki/File:En-us-A.ogg'),
    'Letter B': ('https://upload.wikimedia.org/wikipedia/commons/9/93/En-us-b.ogg',
             'En-us-b.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-b.ogg'),
    'Letter C': ('https://upload.wikimedia.org/wikipedia/commons/5/5c/En-us-c.ogg',
             'En-us-c.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-c.ogg'),
    'Letter D': ('https://upload.wikimedia.org/wikipedia/commons/8/80/En-us-d.ogg',
             'En-us-d.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-d.ogg'),
    'Letter E': ('https://upload.wikimedia.org/wikipedia/commons/1/18/En-us-e.ogg',
             'En-us-e.ogg by Logictheo - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-e.ogg'),
    'Letter F': ('https://upload.wikimedia.org/wikipedia/commons/7/71/En-us-f.ogg',
             'En-us-f.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-f.ogg'),
    'Letter G': ('https://upload.wikimedia.org/wikipedia/commons/0/06/En-us-g.ogg',
             'En-us-g.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-g.ogg'),
    'Letter H': ('https://upload.wikimedia.org/wikipedia/commons/d/d1/En-us-h.ogg',
             'En-us-h.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-h.ogg'),
    'Letter I': ('https://upload.wikimedia.org/wikipedia/commons/9/9f/En-us-I.ogg',
             'En-us-I.ogg by unknown speaker - Public domain - https://commons.wikimedia.org/wiki/File:En-us-I.ogg'),
    'Letter J': ('https://upload.wikimedia.org/wikipedia/commons/7/7e/En-us-j.ogg',
             'En-us-j.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-j.ogg'),
    'Letter K': ('https://upload.wikimedia.org/wikipedia/commons/8/8d/En-us-k.ogg',
             'En-us-k.ogg by Neskaya - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-k.ogg'),
    'Letter L': ('https://upload.wikimedia.org/wikipedia/commons/9/95/En-us-L.ogg',
             'En-us-L.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-L.ogg'),
    'Letter M': ('https://upload.wikimedia.org/wikipedia/commons/4/44/En-us-m.ogg',
             'En-us-m.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-m.ogg'),
    'Letter N': ('https://upload.wikimedia.org/wikipedia/commons/7/71/En-us-n.ogg',
             'En-us-n.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-n.ogg'),
    'Letter O': ('https://upload.wikimedia.org/wikipedia/commons/e/e9/En-us-O.ogg',
             'En-us-O.ogg by DroEsperanto - Public domain - https://commons.wikimedia.org/wiki/File:En-us-O.ogg'),
    'Letter P': ('https://upload.wikimedia.org/wikipedia/commons/7/79/En-us-p.ogg',
             'En-us-p.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-p.ogg'),
    'Letter Q': ('https://upload.wikimedia.org/wikipedia/commons/6/6f/En-us-q.ogg',
             'En-us-q.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-q.ogg'),
    'Letter R': ('https://upload.wikimedia.org/wikipedia/commons/7/75/En-us-r.ogg',
             'En-us-r.ogg by Logictheo - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-r.ogg'),
    'Letter S': ('https://upload.wikimedia.org/wikipedia/commons/5/54/En-us-s.ogg',
             'En-us-s.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-s.ogg'),
    'Letter T': ('https://upload.wikimedia.org/wikipedia/commons/8/8d/En-us-t.ogg',
             'En-us-t.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-t.ogg'),
    'Letter U': ('https://upload.wikimedia.org/wikipedia/commons/9/9d/En-us-u.ogg',
             'En-us-u.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-u.ogg'),
    'Letter V': ('https://upload.wikimedia.org/wikipedia/commons/3/3a/En-us-v.ogg',
             'En-us-v.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-v.ogg'),
    'Letter W': ('https://upload.wikimedia.org/wikipedia/commons/4/4b/En-us-w.ogg',
             'En-us-w.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-w.ogg'),
    'Letter X': ('https://upload.wikimedia.org/wikipedia/commons/b/bd/En-us-X.ogg',
             'En-us-X.ogg by Sylvanmoon - CC BY-SA 4.0 - https://commons.wikimedia.org/wiki/File:En-us-X.ogg'),
    'Letter Y': ('https://upload.wikimedia.org/wikipedia/commons/d/dd/En-us-y.ogg',
             'En-us-y.ogg by Twocs - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-y.ogg'),
    'Letter Z': ('https://upload.wikimedia.org/wikipedia/commons/0/0f/En-us-z.ogg',
             'En-us-z.ogg by Dvortygirl - CC BY-SA 3.0 - https://commons.wikimedia.org/wiki/File:En-us-z.ogg'),
    'peekaboo': ('https://upload.wikimedia.org/wikipedia/commons/6/63/LL-Q1860_%28eng%29-Vealhurl-peekaboo.wav',
             'LL-Q1860 (eng)-Vealhurl-peekaboo.wav by Vealhurl - CC BY-SA 4.0 - https://commons.wikimedia.org/wiki/File:LL-Q1860_(eng)-Vealhurl-peekaboo.wav'),
}

SHARED = {"Foot": "Shoe"}  # sound effects reused from another object
TARGET_RMS = 0.16  # similar loudness for every clip (before extra gain)


def download(url, path):
    headers = WIKI_UA if "wikimedia.org" in url else UA
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 7:
                raise
            time.sleep(60 * (attempt + 1))  # Wikimedia rate limit: back off
    with open(path, "wb") as f:
        f.write(data)
    if "wikimedia.org" in url:
        time.sleep(8)  # Wikimedia throttles bulk downloads; go slowly


def decode_mono(path):
    """Decode any format pygame can read to a list of mono floats at RATE."""
    raw = array.array("h", pygame.mixer.Sound(path).get_raw())
    _rate, _size, channels = pygame.mixer.get_init()
    if channels == 1:
        return [s / 32768 for s in raw]
    return [(raw[i] + raw[i + 1]) / 65536 for i in range(0, len(raw) - 1, channels)]


def best_window(x, seconds, threshold=0.08):
    """Loudest stretch of the recording, then trimmed to where the sound actually is."""
    n = int(seconds * RATE)
    block = 1024
    env = [math.sqrt(sum(v * v for v in x[i:i + block]) / block) for i in range(0, max(1, len(x) - block), block)]
    per = max(1, n // block)
    if len(env) <= per:
        start = 0
    else:
        acc = sum(env[:per])
        best, best_i = acc, 0
        for i in range(per, len(env)):
            acc += env[i] - env[i - per]
            if acc > best:
                best, best_i = acc, i - per + 1
        start = best_i * block
    seg = x[start:start + n]
    peak = max((abs(v) for v in seg), default=0) or 1
    loud = [i for i, v in enumerate(seg) if abs(v) > peak * threshold]
    if loud:  # drop quiet lead-in/tail, keep a tiny margin
        seg = seg[max(0, loud[0] - int(0.03 * RATE)):loud[-1] + int(0.1 * RATE)]
    return seg


def level(seg, gain, fade_out=0.25):
    active = [v for v in seg if abs(v) > 0.01] or seg
    rms = math.sqrt(sum(v * v for v in active) / len(active)) or 1
    k = TARGET_RMS / rms * gain
    peak = max(abs(v) for v in seg) * k
    if peak > 0.9:  # never clip
        k *= 0.9 / peak
    fade_in, fade_out = int(0.02 * RATE), int(fade_out * RATE)
    out = []
    for i, v in enumerate(seg):
        f = min(1.0, i / fade_in, (len(seg) - i) / fade_out)
        out.append(int(max(-1, min(1, v * k * f)) * 32767))
    return out


def save(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(array.array("h", samples).tobytes())


def fetch(url, dest, process):
    tmp = os.path.join(tempfile.gettempdir(), "babysmash_" + url.rsplit("/", 1)[-1])
    download(url, tmp)
    seg = process(decode_mono(tmp))
    save(dest, seg)
    os.remove(tmp)
    print(f"{os.path.basename(dest):16} {len(seg) / RATE:4.1f} s  <- {urllib.request.unquote(url.rsplit('/', 1)[-1])}")


def main():
    words_dir = os.path.join(OUT, "words")
    os.makedirs(words_dir, exist_ok=True)
    pygame.mixer.pre_init(RATE, -16, 1)
    pygame.init()
    for word, (url, _credit, seconds, gain) in PICKS.items():
        dest = os.path.join(OUT, f"{word}.wav")
        if not os.path.exists(dest):
            fetch(url, dest, lambda x: level(best_window(x, seconds), gain))
    for word, source in SHARED.items():
        dest = os.path.join(OUT, f"{word}.wav")
        if not os.path.exists(dest) and os.path.exists(os.path.join(OUT, f"{source}.wav")):
            shutil.copyfile(os.path.join(OUT, f"{source}.wav"), dest)
            print(f"{word}.wav           copied from {source}.wav")
    for word, (url, _credit) in WORDS.items():
        dest = os.path.join(words_dir, f"{word}.wav")
        if not os.path.exists(dest):  # keep the whole word; gentle trim so soft endings survive
            fetch(url, dest, lambda x: level(best_window(x, 3.0, threshold=0.03), 1.0, fade_out=0.04))
    with open(os.path.join(OUT, "CREDITS.txt"), "w", encoding="utf-8") as f:
        f.write("Baby Smash uses these recordings (trimmed and volume-levelled).\n\n")
        f.write("SPOKEN WORDS (sounds/words/)\n")
        for word, (_url, credit) in WORDS.items():
            f.write(f"{word}: {credit}\n")
        f.write("\nSOUND EFFECTS (sounds/)\n")
        for word, (_url, credit, _s, _g) in PICKS.items():
            f.write(f"{word}: {credit}\n")
        for word, source in SHARED.items():
            f.write(f"{word}: same recording as {source}\n")


if __name__ == "__main__":
    main()

