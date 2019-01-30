# -*- coding: utf-8 -*-
from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Sources.Event import  Event

from Components.Sources.ExtEvent import ExtEvent
from Components.Sources.extEventInfo import extEventInfo
from Components.Sources.ServiceEvent import  ServiceEvent
from Tools.MovieInfoParser import getExtendedMovieDescription
from ServiceReference import ServiceReference
import json
import HTMLParser
import re

import logging

class ScroungerExtEventEPG(Converter, object):
	#Input Parameter per Skin	
	IS_EPGSHARE_AVAILABLE = "IsEpgShareAvailable"
	EPGSHARE_RAW = "EpgShareRaw"
	EPISODE_NUM = "EpisodeNum"
	TITLE = "Title"								# optional mit Prefix angabe -> z.B. Titel oder Titel(Titel:)
	SUBTITLE = "Subtitle"						# mit MaxWord angabe -> z.B. Subtitle(10)
	PARENTAL_RATING = "ParentalRating"			# optional mit Prefix angabe -> z.B. ParentalRating oder ParentalRating(FSK)
	GENRE = "Genre"								# optional mit Prefix angabe -> z.B. Genre oder Genre(Genre:)
	YEAR = "Year"								# optional mit Prefix angabe -> z.B. Year oder Year(Jahr:)
	COUNTRY = "Country"							# optional mit Prefix angabe -> z.B. Country oder Country(Land:)
	RATING = "Rating"							# (nur EpgShare) optional mit Prefix angabe -> z.B. Rating(Bewertung)
	RATING_STARS = "RatingStars"				# (nur EpgShare) optional mit Prefix angabe -> z.B. RatingStars(star) -> Output: 65 -> kann für Images verwendet werden
	CATEGORY = "Category"						# (nur EpgShare) optional mit Prefix angabe -> z.B. Rating(Bewertung)
	
	#Parser fuer Serien- und Episodennummer
	seriesNumParserList = [('(\d+)[.]\sStaffel[,]\sFolge\s(\d+)'), 
							_('(\d+)[.]\sStaffel[,]\sEpisode\s(\d+)'),
							_('(\d+)[.]\sEpisode\sder\s(\d+)[.]\sStaffel'),
							_('[(](\d+)[.](\d+)[)]')]
	
	htmlParser = HTMLParser.HTMLParser()
	
	
	SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE = 0
	SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE = 1
	SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR = 2
	SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY = 3
	
	def __init__(self, type):
		Converter.__init__(self, type)
		
		self.log = self.initializeLog()

		self.inputString = type
		self.types = str(type).split(",")
		
	@cached
	def getText(self):
		self.log.info('getText: inputString: %s (%s)', str(self.inputString), len(self.types))
		
		extraData = self.getExtraData()
		
		try:
			event = self.source.event[0]
		except:
			event = None
		
		values = self.deserializeJson(extraData)
		values = None
		
		if self.types != '':
			result = []
			try:
				for type in self.types:
					type.strip()
					self.logType = type
					
					if type == self.IS_EPGSHARE_AVAILABLE:
						#Prüfen ob EpgShare Daten zur Verfügung stehen
						if(values != None and len(values) > 0):
							return 'true'
						else:
							return 'false'
					elif type == self.EPGSHARE_RAW:
						#alle Daten aus der Datenbank ausgeben
						return self.getExtraData()
					elif type == self.EPISODE_NUM:
						episodeNum = self.getEpisodeNum(event, values)
						if (episodeNum != None):
							result.append(episodeNum)
					elif self.TITLE in type:
						title = self.getTitleWithPrefix(type, event, values)
						if(title != None and len(title) > 0 and title != ' '):
							result.append(title)					
					elif self.SUBTITLE in type:
						subtitle = self.getSubtitle(type, event, values)
						if(subtitle != None and len(subtitle) > 0 and subtitle != ' '):
							result.append(subtitle)
					elif self.PARENTAL_RATING in type:
						parentialRating = self.getParentalRating(type, event, values)
						if(parentialRating != None):
							result.append(parentialRating)
					elif self.RATING in type:
						rating = None
						if(self.RATING_STARS in type):
							#gerundetes Rating, kann z.B. für Rating Images verwendet werden
							rating = self.getRating(type, values, True)
						else:
							#Rating als Kommazahl
							rating = self.getRating(type, values, False)
						
						if(rating != None):
							result.append(rating)
					elif self.CATEGORY in type:
						category = self.getCategory(type, values)
						if(category != None):
							result.append(category)
					elif self.GENRE in type:
						genre = self.getGenre(type, values, event)
						if(genre != None):
							result.append(genre)
					elif self.YEAR in type:
						year = self.getYear(type, values, event)
						if(year != None):
							result.append(year)
					elif self.COUNTRY in type:
						country = self.getCountry(type, values, event)
						if(country != None):
							result.append(country)							
						
					else:
						result.append("!!! invalid parameter '%s' !!!" % (type))

				sep = ' %s ' % str(self.htmlParser.unescape('&#xB7;'))
				return sep.join(result)					
			except Exception, e:
				self.log.error("getText: '%s'  %s", self.logType, str(e))
				return "[Error] getText: '%s'  %s" % (self.logType, str(e))					
					
		return ""
		
	text = property(getText)
	
	def getCountry(self, type, values, event):
		country = None
		
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'country' in values:
				if len(str(values['country']).strip()) > 0:
					country = str(values['country']).strip()

		if (country == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren	

			desc = event.getShortDescription()
			
			if(desc == ''):
				#Rückfalllösung über FullDescription
				desc = self.getFullDescription(event)
			
			if desc != "":			
				#Spezielle EPG Formate parsen
				parsedDesc = self.getSpecialFormatDescription(desc, self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY)				
				if(parsedDesc != None):
					country = parsedDesc

			#country aus FullDescription parsen -> Foromat ' xx Min.\n Land Jahr'
			if(country == None):
				country = self.getParsedCountryOrYear(self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY, event.getExtendedDescription(), event)					
					
		prefix = self.getPrefixParser(type)
		if(country != None and prefix != None):
			country = '%s %s' % (prefix, country)
			
		return country
	
	def getYear(self, type, values, event):
		year = None

		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'year' in values:
				if len(str(values['year']).strip()) > 0:
					year = str(values['year']).strip()
					
		if (year == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren
			
			desc = event.getShortDescription()
			
			if(desc == ''):
				#Rückfalllösung über FullDescription
				desc = self.getFullDescription(event)
			
			if desc != "":			
				#Spezielle EPG Formate parsen
				parsedDesc = self.getSpecialFormatDescription(desc, self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR)				
				if(parsedDesc != None):
					year = parsedDesc
					
			#Year aus FullDescription parsen -> Foromat ' xx Min.\n Land Jahr'
			if(year == None):
				year = self.getParsedCountryOrYear(self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR, event.getExtendedDescription(), event)
		
		prefix = self.getPrefixParser(type)
		if(year != None and prefix != None):
			year = '%s %s' % (prefix, year)
	
		return year
	
	def getGenre(self, type, values, event):
		genre = None

		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'genre' in values:
				if len(str(values['genre']).strip()) > 0:
					genre = str(values['genre']).strip()
					
		if (genre == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren
			
			desc = event.getShortDescription()
			
			if(desc == ''):
				#Rückfalllösung über FullDescription
				desc = self.getFullDescription(event)

			if desc != "":			
				#Spezielle EPG Formate parsen
				parsedDesc = self.getSpecialFormatDescription(desc, self.SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE)				
				if(parsedDesc != None):
					genre = parsedDesc						

		prefix = self.getPrefixParser(type)
		if(genre != None and prefix != None):
			genre = '%s %s' % (prefix, genre)
		
		return genre

	def getCategory(self, type, values):
		category = None
		
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'categoryName' in values:
				if len(str(values['categoryName']).strip()) > 0:
					category = str(values['categoryName']).strip()
					
		prefix = self.getPrefixParser(type)
		if(category != None and prefix != None):
			category = '%s %s' % (prefix, category)
		
		return category
	
	def getRating(self, type, values, isStars):
		rating = None
		
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'vote' in values:
				if len(str(values['vote']).strip()) > 0:
					tmp = str(values['vote']).strip()
					
					if(self.isNumber(tmp)):
						# Nur anzeigen wenn Rating > 0
						if(float(tmp) > 0):
							if(isStars):
								rating = str(round(float(tmp) * 2) / 2).replace(".","")
							else:
								rating = tmp.replace(".",",")
						else:
							if(isStars):
								rating = str(0)
					else:
						if(isStars):
							rating = str(0)					

		prefix = self.getPrefixParser(type)
		if(rating != None and prefix != None):
			rating = '%s %s' % (prefix, rating)
					
		return rating
	
	def getParentalRating(self, type, event, values):				
		parentialRating = None
		
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden
			if 'ageRating' in values:
				if len(str(values['ageRating']).strip()) > 0:
					tmp = str(values['ageRating']).strip()
					
					if(tmp == 'OhneAltersbeschränkung'):
						parentialRating = str(0)
					elif(tmp != 'Unbekannt'):
						parentialRating = tmp
		
		if (parentialRating == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren
			desc = self.getFullDescription(event)

			parser = re.search('Ab\s(\d+)\s[Jahren|Jahre]', desc)
			if(parser):
				parentialRating = parser.group(1)
		
		prefix = self.getPrefixParser(type)
		if(parentialRating != None and prefix != None):
			parentialRating = '%s %s' % (prefix, parentialRating)
		
		return parentialRating		
			
	def getTitle(self, event, values):
		#Nur Title ohne Prefix, wird zum vergleichen benötigt
		title = None
				
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden				
			if len(str(values['title']).strip()) > 0:
				title = str(values['title']).strip()
						
		if (title == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren
			title = event.getEventName()		
				
		return title
		
	def getTitleWithPrefix(self, type, event, values):
		title = self.getTitle(event, values)

		prefix = self.getPrefixParser(type)
		if(title != None and prefix != None):
			title = '%s %s' % (prefix, title)				
				
		return title		
	
	def getSubtitle(self, type, event, values):
		subtitle = None
		
		if(values != None and len(values) > 0):
		#EpgShare Daten in DB vorhanden	
			if len(str(values['subtitle']).strip()) > 0:
				subtitle= str(values['subtitle']).strip()
			
		if (subtitle == None and event != None):
		#Keine EpgShare Daten in DB vorhanden, aus Descriptions extrahieren
			try:
				maxWords = int(self.getMaxSubtitleWords(type))
				result = self.getSubtitleFromDescription(event, maxWords)
				if (result != None):						
					subtitle = result
			except Exception, ex:
				subtitle = str(ex)
		
		return subtitle
		
	def getSubtitleFromDescription(self, event, maxWords):
		try:		
			desc = event.getShortDescription()
			
			if(desc == ''):
				#Rückfalllösung über FullDescription
				desc = self.getFullDescription(event)

			if (desc != ""):				
				#Spezielle EPG Formate parsen
				parsedDesc = self.getSpecialFormatDescription(desc, self.SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE)				
				if(parsedDesc != None):
					return parsedDesc

				#maxWords verwenden				
				self.log.debug("getSubtitleFromDescription")
				result = self.getMaxWords(desc, maxWords)			
				if(result != None):
					
					genre = self.getCompareGenreWithGenreList(result, None)
					if(genre != None):
					#Prüfen Subtitle = Genre, dann nichts zurück geben
						if(genre == result):
							self.log.debug("getSubtitleFromDescription (1): %s is genre: %s", desc, genre)
							return None
					
					self.log.debug("getSubtitleFromDescription (1): %s -> Subtitle: %s", desc, result)
					return result
				else:			
				#Wenn Wörter in shortDescription > maxWords, dann nach Zeichen suchen und bis dahin zurück geben und prüfen ob < maxWord EXPERIMENTAL
					return self.getSubtitleFromDescriptionUntilChar(event, desc, maxWords)

			else:
				return None
		except Exception, e:
			return "[Error] getSubtitleFromDescription: %s" % (str(e))
		
		return None
	
	def getSpecialFormatDescription(self, desc, resultTyp):
		#Spezielle Formate raus werfen
		desc = desc.replace("Thema u. a.: ","")
	
		wordList = desc.split(", ")
		
		#Format: 'Subtitle, Genre, Land Jahr'
		if len(wordList) == 3:		
			parser = re.match('^[^.:?;]+[,]\s[^.:?;]+[,]\s[^.:?;]+\s\d+$', desc)
			
			if (desc.count(", ") == 2 and parser):
				#Pruefen 2x ', ' vorhanden ist und ob letzter Eintrag im Format 'Land Jahr'
				#return desc.replace(", ", " %s " % str(self.htmlParser.unescape('&#xB7;')))				
				if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE):
					self.log.debug("getSpecialFormatDescription (1): %s -> Subtitle: %s", desc, wordList[0])
					return wordList[0]
				elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE):
					self.log.debug("getSpecialFormatDescription (1): %s -> Genre: %s", desc, wordList[1])
					return wordList[1]
				elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
					year = self.getParsedCountryOrYear(resultTyp, wordList[2], None)
					if(year != None):
						self.log.debug("getSpecialFormatDescription (1): %s -> Year: %s", desc, year)
						return year
				elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY):
					country = self.getParsedCountryOrYear(resultTyp, wordList[2], None)
					if(country != None):
						self.log.debug("getSpecialFormatDescription (1): %s -> Country: %s", desc, country)
						return country					
		
		#Format: 'Subtitle/Genre, Land Jahr' | 'Genre, Land Jahr' | 'Subtitle Genre, Land Jahr'
		#TODO: Abgleich mit Genre einfügen
		elif len(wordList) == 2:
			parser = re.match('^[^.:?!;]+[,]\s[^.:?!;]+\s\d+$', desc)
			
			if (desc.count(", ") == 1 and parser):

				genre = self.getCompareGenreWithGenreList(wordList[0], ', ')
				if(genre != None):
				#Format 'Genre, Land Jahr'
				#Prüfen ob Wort vor Koma in Genre List ist -> Genre
					if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE):
						self.log.debug("getSpecialFormatDescription (2): %s -> Subtitle: %s", desc, None)
						return ''
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE):
						self.log.debug("getSpecialFormatDescription (2): %s -> Genre: %s", desc, wordList[0])
						return wordList[0]
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
						year = self.getParsedCountryOrYear(resultTyp, wordList[1], None)
						if(year != None):
							self.log.debug("getSpecialFormatDescription (2): %s -> Year: %s", desc, year)
							return year
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY):
						country = self.getParsedCountryOrYear(resultTyp, wordList[1], None)
						if(country != None):
							self.log.debug("getSpecialFormatDescription (2): %s -> Country: %s", desc, country)
							return country

				#Format 'Subtitle Genre, Land Jahr'
				#Genre herausfiltern						
				genre = self.getCompareGenreWithGenreList(wordList[0], None)
				if(genre != None):
					subtitle = wordList[0].replace(genre + ". ","").replace(genre,"").strip()
					
					if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE):
						if(len(subtitle) > 0):
							self.log.debug("getSpecialFormatDescription (3): %s -> Subtitle: %s", desc, subtitle)
						else:
							self.log.debug("getSpecialFormatDescription (3): %s -> Subtitle: %s", desc, None)
							
						return subtitle
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE):
						self.log.debug("getSpecialFormatDescription (3): %s -> Genre: %s", desc, genre)
						return genre
						
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
						year = self.getParsedCountryOrYear(resultTyp, wordList[1], None)
						if(year != None):
							self.log.debug("getSpecialFormatDescription (3): %s -> Year: %s", desc, year)
							return year
					
					elif (resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY):
						country = self.getParsedCountryOrYear(resultTyp, wordList[1], None)
						if(country != None):
							self.log.debug("getSpecialFormatDescription (3): %s -> Country: %s", desc, country)
							return country						
				
				if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_SUBTITLE):
				#Format 'Subtitle, Land Jahr'
					self.log.debug("getSpecialFormatDescription (4): %s -> Subtitle: %s", desc, wordList[0])
					return wordList[0]					
		
		#Wird nur für Genre angewendet
		if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_GENRE):
			genre = self.getCompareGenreWithGenreList(desc, None)
			if(genre != None):
				self.log.debug("getSpecialFormatDescription (5): %s -> Genre: %s", desc, genre)
				return genre
					
		return None
	
	def getSubtitleFromDescriptionUntilChar(self, event, desc, maxWords):
		#Wenn Wörter in shortDescription > maxWords, dann nach Zeichen suchen und bis dahin zurück geben und prüfen ob < maxWord EXPERIMENTAL		
		firstChar = re.findall('[.]\s|[?]\s|[:]\s|$', desc)[0]
		if(firstChar != "" and len(firstChar) > 0):
			firstCharPos = desc.find(firstChar)
			result = desc[0:firstCharPos]			
			
			#Kann ggf. Genre sein, dann raus filtern
			genre = self.getCompareGenreWithGenreList(result, ". ")
			if(genre != None):
				if(genre == result):
					#genre = genre + "."
					desc = desc.replace(genre + ". ","")
					firstCharPos = desc.find(firstChar)
					result = desc[0:firstCharPos]
					
					#maxWords verwenden
					result = self.getMaxWords(result, maxWords)			
					if(result != None):
						self.log.debug("getSubtitleFromDescriptionUntilChar (1): %s -> Subtitle: %s", desc, result)
						return result
					
			#maxWords verwenden
			if(result != None):
				result = self.getMaxWords(result, maxWords)			
				if(result != None):
					self.log.debug("getSubtitleFromDescriptionUntilChar (2): %s -> Subtitle: %s", desc, result)
					return result
		
		return None
		
	def getMaxWords(self, desc, maxWords):
		try:			
			wordList = desc.split(" ")
			if (len(wordList) <= maxWords):
				del wordList[maxWords:len(wordList)]
				sep = ' '
				result = sep.join(wordList)	
				
				return result
		
		except Exception, e:
			self.log.error("getMaxWords: %s", (str(e)))
			return "[Error] getMaxWords: %s" % (str(e))
			
		return None
	
	def getMaxSubtitleWords(self, type):
		#max Anzahl an erlaubten Wörten aus Parameter von Skin lesen
		maxSubtitleWordsParser = 'Subtitle[(](\d+)[)]'
		maxSubtitleWords = re.search(maxSubtitleWordsParser, type)
		
		if(maxSubtitleWords):
			return maxSubtitleWords.group(1)
		else:
			return "!!! invalid type '%s' !!!" % (type)
	
	def getEpisodeNum(self, event, values):
		episodeNum = None
		
		if(values != None and len(values) > 0):
			#EpgShare Daten sind in DB vorhanden
			if 'season' in values and 'episode' in values:
				if len(str(values['season']).strip()) > 0 and len(str(values['episode']).strip()) > 0:
					episodeNum = "S%sE%s" % (str(values['season']).zfill(2), str(values['episode']).zfill(2))
	
		if (episodeNum == None and event != None):
			#Keine EpgShare Daten in DB vorhanden, versuch über Parser	
			desc = self.getFullDescription(event)

			for parser in self.seriesNumParserList:
				extractSeriesNums = re.search(parser, desc)

				if(extractSeriesNums):
					sNum = extractSeriesNums.group(1)
					eNum = extractSeriesNums.group(2)

					return 'S%sE%s' % (sNum.zfill(2), eNum.zfill(2))
			
		return episodeNum
		
	def getFullDescription(self, event):
	
		desc = None
		ext_desc = event.getExtendedDescription()
		short_desc = event.getShortDescription()
		if short_desc == "":
			return ext_desc
		elif ext_desc == "":
			return short_desc
		else:
			return "%s\n\n%s" % (short_desc, ext_desc)

	def getPrefixParser(self, type):
		#Prefix aus Parameter von Skin lesen
		prefixParser = '.*[(](.*)[)]'
		prefix = re.search(prefixParser, type)
		
		if(prefix):
			return prefix.group(1)
		else:
			return None			

	def deserializeJson(self, extraData):
		#Daten aus DB deserializieren
		try:
			if str(extraData) != '':
				return json.loads(extraData)
		except Exception, ex:
			return None	
			
	def getExtraData(self):
		if self.source.event:
			if type(self.source) == ExtEvent:
				try:
					starttime = self.source.event.getBeginTime()
					title = self.source.event.getEventName()
					return json.dumps(self.getDataFromDatabase(str(self.source.service), str(self.source.event.getEventId()), starttime, title))
				except Exception, ex:
					self.log.error('getExtraData (1): %s', str(ex))
					return "Error1: %s" % str(ex)
			elif str(type(self.source)) == "<class 'Components.Sources.extEventInfo.extEventInfo'>":
				try:
					return json.dumps(self.getDataFromDatabase(str(self.source.service), str(self.source.eventid)))
				except Exception, ex:
					self.log.error('getExtraData (2): %s', str(ex))
					return "Error2: %s" % str(ex)
			elif hasattr(self.source, 'service'):
				try:
					service = self.source.getCurrentService()
					servicereference = ServiceReference(service)
					return json.dumps(self.getDataFromDatabase(str(servicereference), str(self.source.event.getEventId())))
				except Exception, ex:
					self.log.error('getExtraData (2): %s', str(ex))
					return "Error3: %s" % str(ex)
			elif type(self.source) == Event:
				return self.source.event.getExtraEventData()
		return ""
		
	def getDataFromDatabase(self, service, eventid, beginTime=None, EventName= None):
		try:
			from Plugins.Extensions.EpgShare.main import getEPGDB
			data = None
			if "::" in str(service):
				service = service.split("::")[0] + ":"
			if "http" in str(service):
				service = service.split("http")[0]
			if not "1:0:0:0:0:0:0:0:0:0:" in service and not "4097:0:0:0:0:0:0:0:0:0:" in service:
				if beginTime and EventName:
					data = getEPGDB().selectSQL("SELECT * FROM epg_extradata WHERE ref = ? AND (eventid = ? or (LOWER(title) = ? and airtime BETWEEN ? AND ?))", [str(service), str(eventid),str(EventName.lower()).decode("utf-8"), str(int(beginTime) -120), str(int(beginTime) + 120) ])
				else:
					data = getEPGDB().selectSQL("SELECT * FROM epg_extradata WHERE ref = ? AND eventid = ?", [str(service), str(eventid)])
				if data and len(data) > 0:
					return data[0]
				else:
					return None
			else:
				return None
		except Exception, ex:
			print "DB Error: %s" % str(ex)
			return None
		except ImportError, exi:
			print "Import Error: %s" % str(exi)
			return None		

	def isNumber(self, inp):
		try:
			val = int(inp)
			return True
		except ValueError:
			try:
				val = float(inp)
				return True
			except ValueError:
				return False
			
	def initializeLog(self):
		logger = logging.getLogger("ScroungerExtEventName")
		logger.setLevel(logging.DEBUG)

		# create a file handler
		handler = logging.FileHandler('/tmp/meins.log')
		handler.setLevel(logging.DEBUG)

		# create a logging format
		formatter = logging.Formatter('%(asctime)s - %(name)s: [%(levelname)s] %(message)s')
		handler.setFormatter(formatter)

		# add the handlers to the logger
		logger.addHandler(handler)

		logger.debug("logger initialized")
		
		return logger
		
	def getCompareGenreWithGenreList(self, desc, splitChar):
		
		if(splitChar == None):
			desc = re.sub('[.,]', '', desc)			#Hinter Genre kann direkt ein Zeichen folgen
			descWordList = desc.split(' ')
		else:
			descWordList = desc.split(splitChar)		#WortList zum Vergleichen erzeugen
		
		setWordList = set(descWordList)
		
		#exakten Treffer suchen
		for genre in self.AVAILABLE_GENRES_EPG:
			setGenre = set([genre])
			if setGenre & setWordList:
				return genre
		
		#if(desc in self.AVAILABLE_GENRES_EPG):
		#Description ist Genre (ein Wort)
			#return desc
		
		#for genre in self.AVAILABLE_GENRES_EPG:
			#Genre herausfiltern
			#if(genre in desc):
				#return genre

		return None
		
	def getParsedCountryOrYear(self, resultTyp, desc, event):
		
		if(event == None):
		#verwendet von getSpecialFormatDescription
			parser = re.match('^([^.:?; ]+)\s(\d+)$', desc)
			if(parser):
				if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY):
					return parser.group(1)
				elif(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
					return parser.group(2)
		else:
			if(desc != ""):
				parser = re.search('\s\d+\s[Min.]+\n([^.:?;]+)\s(\d+)', desc)
				if(parser):
					if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_COUNTRY):
						return parser.group(1)
					elif(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
						return parser.group(2)
				
				parser =re.search('\s\d+\s[Min.]+\n(\d+)', desc)
				if(parser):
					if(resultTyp == self.SPECIAL_FORMAT_PARSED_DESCRIPTION_YEAR):
						return parser.group(1)
				
		
		return None
		
	AVAILABLE_GENRES_EPG =[
                        "Actionfilm", "Abenteuerfilm", "Animationsfilm", "Animationsserie", "Abenteuer", "Animations-Serie", "Actiondrama", "Abenteuer-Serie", "Actionthriller", "Actionkomödie", "Actionserie", "Animation", "Action",
						"Beziehungskomödie", "Biographie", "Biografie",
						"Comedy", "Clipshow", "Comedy-Serie", "Comedy Show", 
    					"Doku-Reihe", "Doku-Serie", "Dramaserie", "Dokutainment-Reihe", "Dokumentationsreihe", "Dokumentarserie", "Dokumentation", "Drama", "Dokumentarfilm", "Doku-Experiment", "Deutsche Komödie", "Dramedy", "Dokumentarreihe", "Dokureihe",
    					"Ermittler-Doku",
    					"Familienserie", "Familienkomödie", "Familienfilm", "Fantasyfilm", "Fantasy-Abenteuerfilm", "Familien-Serie", "Fantasy", "Familiendrama", "Fantasy-Action",
    					"Horrorfilm", "Horror-Serie", "Horrorthriller", "Heimatserie", "Horrorkomödie", 
    					"Infotainment", "Informationssendung", "Information",
    					"Kinderserie", "Krimi", "Kochshow", "Kinder-Komödie", "Krimiserie", "Komödie", "Koch-Doku", "Krimikömödie", "Krimikomödie", "Kriegsdrama", "Kriminalfilm", "Krankenhaus-Soap", "Kriegsfilm", 
						"Liebeskomödie", "Liebesgeschichte", "Liebesdrama", "Liebesfilm", "Liebesdramödie",
    					"Mysterythriller", "Magazin", "Mysteryfilm",
						"Naturdokumentarreihe",
						"Polizeiserie", "Psychothriller",
						"Quizshow",
    					"Romanze", "Reportagemagazin", "Reportagereihe", "Reportage", "Romantikkomödie", "Romantic Comedy", "Reisedoku", "Reality-TV", "Real Life Doku", "Romantische Komödie", 
    					"Sitcom", "Show", "Science-Fiction-Komödie", "Science-Fiction-Film", "Science-Fiction-Horror", "Scripted Reality", "Sketch-Comedy", "Spielfilm", "Sport", "Science-Fiction-Serie", "Sci-Fi-Serie", 
    					"Teleshopping", "Thriller", "Talkshow", "Telenovela", "Thrillerkomödie", "Tragikomödie", 
						"Unterhaltungs-Show", 
    					"Werbesendung", "Western", "Wissensmagazin", "Wissenschaftsmagazin", "Westernkomödie", 
						"Zeichentrick-Serie", "Zeichentrickfilm",
                    ]