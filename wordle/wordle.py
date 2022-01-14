#!/usr/bin/python
# coding=utf-8
import os
import re
import sys
import time
import json
import copy
import string
import logging
import datetime
import requests
import calendar
import argparse
import temp_bot

if __name__ == "__main__":
	# Argument Parser
	apParser = argparse.ArgumentParser()
	apParser.add_argument("--debug", action='store_true', help="Debug mode")
	apParser.add_argument("--mode", nargs="+", help="mode1/mode2")
	apArguments = apParser.parse_args()

	class Formatter(logging.Formatter):
		def __init__(self, f, ft, exc):
			self.formatter = logging.Formatter(f, ft)
			self.exc = exc

		def format(self, record):
			new_record = copy.copy(record)
			if not self.exc:
				new_record.exc_info = ()
			return self.formatter.format(new_record)

	# Logger
	logWordle = logging.getLogger("Wordle")
	logWordle.setLevel(logging.DEBUG)
	logFormat = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S", False)
	logFormatFull = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S", True)
	logHandlerFile = logging.FileHandler("wordle.log", encoding="utf=8")
	logHandlerFileError = logging.FileHandler("wordle.err.log", encoding="utf=8")
	logHandlerStream = logging.StreamHandler(sys.stdout)
	logHandlerFile.setLevel(logging.DEBUG if apArguments.debug else logging.INFO)
	logHandlerFile.setFormatter(logFormat)
	logHandlerFileError.setLevel(logging.ERROR)
	logHandlerFileError.setFormatter(logFormatFull)
	logHandlerStream.setLevel(logging.DEBUG if apArguments.debug else logging.INFO)
	logHandlerStream.setFormatter(logFormatFull)
	logWordle.addHandler(logHandlerFile)
	logWordle.addHandler(logHandlerFileError)
	logWordle.addHandler(logHandlerStream)

	def InitDictionary(aWords):
		dDictionary = {}

		dLetterAppearance = {x: 0 for x in aAlphabetLetters}
		for sWord in aWords:
			for cLetter in set(list(sWord)):
				dLetterAppearance[cLetter] += 1

		dLetterPositions = {"{0}-{1}".format(x, y): {} for (x, y) in [(i, j) for i in range(DEF_WORD_LENGTH) for j in range(i + 1, DEF_WORD_LENGTH + 1) if (i,j) != (0,5)]}
		for sWord in aWords:
			for sRange in dLetterPositions:
				iStart = int(sRange.split("-")[0])
				iEnd = int(sRange.split("-")[1])
				if sWord[iStart:iEnd] not in dLetterPositions[sRange]:
					dLetterPositions[sRange][sWord[iStart:iEnd]] = 0
				dLetterPositions[sRange][sWord[iStart:iEnd]] += 1

		for sWord in aWords:
			dDictionary[sWord] = {}
			iAppearanceScore = 0
			iPositionScore = 0
			for cLetter in set(list(sWord)):
				iAppearanceScore += dLetterAppearance[cLetter]
			for sRange in dLetterPositions:
				iStart = int(sRange.split("-")[0])
				iEnd = int(sRange.split("-")[1])
				iFactor = 1
				iPositionScore += iFactor * dLetterPositions[sRange][sWord[iStart:iEnd]]

			dDictionary[sWord]["appear"] = iAppearanceScore
			dDictionary[sWord]["position"] = iPositionScore

		return dDictionary

	def TruncateDictionary(dDictionary, aValidPositions, dInvalidPositions, aValidLetters):
		aRemovedWords = []
		for sWord in dDictionary:
			bValidWord = True

			if any([x not in sWord for x in dInvalidPositions.keys() ]):
				bValidWord = False
			else:
				for i, cLetter in enumerate(list(sWord)):
					if cLetter not in aValidLetters:
						if cLetter in aValidPositions and aValidPositions[i] == cLetter:
							pass
						else:
							bValidWord = False
					if aValidPositions[i] is not None and aValidPositions[i] != cLetter:
						bValidWord = False
					if cLetter in dInvalidPositions and i in dInvalidPositions[cLetter]:
						bValidWord = False

			if not bValidWord:
				aRemovedWords.append(sWord)

		for sRemovedWord in aRemovedWords:
			dDictionary.pop(sRemovedWord, None)

	def Guess(sWord, sGuess):
		aReturn = [None, None, None, None, None]
		for (i, val) in enumerate(list(sGuess)):
			if val == sWord[i]:
				aReturn[i] = "v"
			elif val not in sWord:
				aReturn[i] = "x"

		aYellowLetters = [sWord[i] for (i, x) in enumerate(aReturn) if x != "v"]
		for (i, val) in enumerate(aReturn):
			if val is None:
				if sGuess[i] in aYellowLetters:
					aReturn[i] = "?"
				else:
					aReturn[i] = "x"

		return "".join(aReturn)

	def Play(sSecret, dDictionary, bInteractive=True, bHardMode=True, bVerbose=False):
		aGuesses = []
		bGuessed = False
		aValidLetters = aAlphabetLetters[:]
		aValidPositions = [None, None, None, None, None]
		dInvalidPositions = {}

		while not bGuessed:
			lambdaSort = lambda x:(x[1]["appear"] + x[1]["position"])
			
			if bVerbose:
				logWordle.debug(sorted(dDictionary.items(), key=lambdaSort))

			sDictionaryTopWord = sorted(dDictionary.items(), key=lambdaSort)[-1][0]
			logWordle.debug("Dictionary top word: {0}".format(sDictionaryTopWord))

			if bInteractive:
				sGuess = input("Your guess: ")
			else:
				sGuess = sDictionaryTopWord

			reMatch = re.match("^[a-z]{5}$", sGuess, re.IGNORECASE)
			if reMatch is None:
				logWordle.error("Invalid word")
			elif sGuess not in dDictionary:
				logWordle.error("Not a dictionary word")
			elif any([x not in aValidLetters and x not in aValidPositions for x in list(sGuess)]):
				logWordle.error("Forbidden letter")
			else:
				sResult = Guess(sSecret, sGuess)
				aGuesses.append(sResult)

				if sResult == "vvvvv":
					bGuessed = True
					logWordle.info("Guessed {0} after {1} attempts.".format(sSecret, len(aGuesses)))
				else:
					for (i, val) in enumerate(list(sResult)):
						if val == "x" and sGuess[i] in aValidLetters:
							aValidLetters.remove(sGuess[i])
						elif val == "?":
							if sGuess[i] not in dInvalidPositions:
								dInvalidPositions[sGuess[i]] = []
							dInvalidPositions[sGuess[i]].append(i)
						elif val== "v":
							if aValidPositions[i] is None:
								aValidPositions[i] = sGuess[i]

					logWordle.debug("Guess result: {0}".format(sResult))
					if bVerbose:
						logWordle.debug("Valid: {0}; Invalid: {1}; Letters: {2}".format(aValidPositions, dInvalidPositions, aValidLetters))

					TruncateDictionary(dDictionary, aValidPositions, dInvalidPositions, aValidLetters)

		return aGuesses

	def Benchmark(aWordles):
		dScores = {}
		for sWordle in aWordles:
			iScore = len(Play(sWordle, dDictionary.copy(), False))
			if iScore not in dScores:
				dScores[iScore] = 0
			dScores[iScore] += 1

		print(dScores)
		fAverage = sum([x*y for x,y in dScores.items()]) / len(aWordles)
		iSuccessfulAttempts = sum([y for x,y in dScores.items() if x <= 6])
		logWordle.info("Average guesses: {0}, Success rate: {1}".format(fAverage, iSuccessfulAttempts / len(aWordles)))

	# Defines
	DEF_WORD_LENGTH = 5

	# Environment Variables

	# Global Variables
	aAlphabetLetters = list(string.ascii_lowercase)

	try:
		with open("dictionary.json", "r") as fInput:
			aWords = json.load(fInput, encoding="utf-8")

		with open("wordle.json", "r") as fInput:
			aWordles = json.load(fInput, encoding="utf-8")

		iTodaysWordle = (datetime.date.today() - datetime.date(2021, 6, 19)).days
		aExcludedWords = aWordles[0:iTodaysWordle]
		dDictionary = InitDictionary([x for x in aWords if x not in aExcludedWords])
		aResult = Play(aWordles[iTodaysWordle], dDictionary.copy(), False, bVerbose=False)

		temp_bot.TelegramMessage("Wordle {0} {1}/6\n\n{2}".format(iTodaysWordle, "X" if len(aResult) > 6 else len(aResult), "\n".join([x.replace("x", "\u2B1C").replace("?", "\U0001F7E8").replace("v", "\U0001F7E9") for x in aResult[0:6]])), apArguments.debug)

		#Benchmark(aWordles[209:250])
	except:
		logWordle.exception("Program Exception!")