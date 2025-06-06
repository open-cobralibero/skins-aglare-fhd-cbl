# -*- coding: utf-8 -*-

from Components.Converter.Converter import Converter
from Components.Element import cached
from enigma import eEPGCache, eServiceReference
from time import localtime, time, mktime, strftime
from datetime import datetime
import logging
import gettext
_ = gettext.gettext
# 2025.04.01 @ lululla fix

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


# Define constants for event types
EPG_SOURCE = 'EPG-SAT.DE'
EVENT_REFERENCE = 'IBDCTSERNX'


class AglareEventName2(Converter, object):
	NAME = 0
	NAME_TWEAKED = 1
	SHORT_DESCRIPTION = 2
	EXTENDED_DESCRIPTION = 3
	FULL_DESCRIPTION = 4
	ID = 5
	NEXT_NAME = 6
	NEXT_DESCRIPTION = 7
	NEXT_NAMEWT = 8
	NEXT_NAME_NEXT = 9
	NEXT_NAME_NEXTWT = 10
	NEXT_EVENT_LIST = 11
	NEXT_EVENT_LISTWT = 12
	NEXT_EVENT_LIST2 = 13
	NEXT_EVENT_LISTWT2 = 14
	NEXT_TIME_DURATION = 15
	PRIME_TIME_NO_DURATION = 16
	PRIME_TIME_ONLY_DURATION = 17
	PRIME_TIME_WITH_DURATION = 18

	def __init__(self, type):
		Converter.__init__(self, type)
		self.epgcache = eEPGCache.getInstance()

		# Map input types to internal constants
		event_types = {
			'NameTweaked': self.NAME_TWEAKED,
			'Description': self.SHORT_DESCRIPTION,
			'ExtendedDescription': self.EXTENDED_DESCRIPTION,
			'FullDescription': self.FULL_DESCRIPTION,
			'ID': self.ID,
			'NextName': self.NEXT_NAME,
			'NextNameNext': self.NEXT_NAME_NEXT,
			'NextNameNextWithOutTime': self.NEXT_NAME_NEXTWT,
			'NextNameWithOutTime': self.NEXT_NAMEWT,
			'NextDescription': self.NEXT_DESCRIPTION,
			'NextEventList': self.NEXT_EVENT_LIST,
			'NextEventListWithOutTime': self.NEXT_EVENT_LISTWT,
			'NextEventList2': self.NEXT_EVENT_LIST2,
			'NextEventListWithOutTime2': self.NEXT_EVENT_LISTWT2,
			'NextTimeDuration': self.NEXT_TIME_DURATION,
			'PrimeTimeNoDuration': self.PRIME_TIME_NO_DURATION,
			'PrimeTimeOnlyDuration': self.PRIME_TIME_ONLY_DURATION,
			'PrimeTimeWithDuration': self.PRIME_TIME_WITH_DURATION,
		}

		self.type = event_types.get(type, self.NAME)

	@cached
	def getText(self):
		event = self.source.event
		if not event:
			return ''

		if self.type == self.NAME:
			return event.getEventName()
		elif self.type == self.NAME_TWEAKED:
			return self.getTweakedEventName(event)
		elif self.type == self.SHORT_DESCRIPTION:
			return event.getShortDescription()
		elif self.type == self.EXTENDED_DESCRIPTION:
			return self.getExtendedDescription(event)
		elif self.type == self.FULL_DESCRIPTION:
			return self.getFullDescription(event)
		elif self.type == self.ID:
			return str(event.getEventId())
		elif self.type in [self.PRIME_TIME_NO_DURATION, self.PRIME_TIME_ONLY_DURATION, self.PRIME_TIME_WITH_DURATION]:
			return self.getPrimeTimeDetails()
		elif self.type in [self.NEXT_NAME, self.NEXT_DESCRIPTION, self.NEXT_TIME_DURATION, self.NEXT_NAMEWT]:
			return self.getNextEventDetails()
		elif self.type in [self.NEXT_EVENT_LIST, self.NEXT_EVENT_LISTWT, self.NEXT_EVENT_LIST2, self.NEXT_EVENT_LISTWT2]:
			return self.getNextEventList()
		return ''

	def getTweakedEventName(self, event):
		description = '%s %s' % (event.getEventName().strip(), event.getShortDescription().strip())
		return description.replace('DOLBY, 16:9', '').replace('(', '').replace(')', '').replace('|', '').replace('0+', '').replace('16+', '').replace('6+', '').replace('12+', '').replace('18+', '')

	def getExtendedDescription(self, event):
		text = event.getShortDescription()
		if text and text[-1] not in ['\n', ' ']:
			text += ' '
		return text + event.getExtendedDescription() or event.getEventName()

	def getFullDescription(self, event):
		description = event.getShortDescription()
		extended = event.getExtendedDescription()
		if description and extended:
			description += '\n'
		return description + extended

	def getPrimeTimeDetails(self):
		reference = self.source.service
		current_event = self.source.getCurrentEvent()
		if current_event:
			now = localtime(time())
			dt = datetime(now.tm_year, now.tm_mon, now.tm_mday, 20, 15)
			target_time = int(mktime(dt.timetuple()))
			self.epgcache.startTimeQuery(eServiceReference(reference.toString()), target_time)
			next_event = self.epgcache.getNextTimeEntry()
			if next_event:
				begin_time = next_event.getBeginTime()
				if begin_time is not None and begin_time <= target_time:
					return self.formatPrimeTimeEvent(next_event)
		return ''

	def formatPrimeTimeEvent(self, event):
		begin_time = event.getBeginTime()
		duration = event.getDuration()
		if begin_time is None or duration is None:
			return ''

		end_time = begin_time + duration
		title = event.getEventName() or ''

		begin_str = strftime('%H:%M', localtime(begin_time))
		end_str = strftime('%H:%M', localtime(end_time))
		DURATION_FORMAT = _('%d min')
		duration_str = DURATION_FORMAT % (duration // 60)

		return "{} - {} ({}) {}".format(begin_str, end_str, duration_str, title)

	def getNextEventDetails(self):
		reference = self.source.service
		info = reference and self.source.info
		if info:
			eventNext = self.epgcache.lookupEvent([EVENT_REFERENCE, (reference.toString(), 1, -1)])
			if eventNext:
				return self.formatNextEvent(eventNext[0])
		return ''

	def formatNextEvent(self, event):
		t = localtime(event[1])
		duration = _('%d min') % (int(0 if event[2] is None else event[2]) / 60)
		if len(event) > 4 and event[4]:
			return f'{t[3]:02d}:{t[4]:02d} ({duration}) {event[4]}'
		return ''

	def getNextEventList(self):
		reference = self.source.service
		info = reference and self.source.info
		if info:
			eventNext = self.epgcache.lookupEvent(['IBDCT', (reference.toString(), 0, -1, -1)])
			if eventNext:
				listEpg = []
				for i, x in enumerate(eventNext):
					if 0 < i < 10 and x[4]:
						t = localtime(x[1])
						duration = _('%d min') % (int(0 if x[2] is None else x[2]) / 60)
						listEpg.append(f'{t[3]:02d}:{t[4]:02d} ({duration}) {x[4]}')
				return '\n'.join(listEpg)
		return ''

	text = property(getText)


"""
# 1. Esempio di Converter per PrimeTimeWithDuration
<screen name="PrimeTimeScreen" position="center,center" size="1280,720" title="Prime Time Events">
	<widget name="primeTimeEvent" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="gold" valign="center">
		<convert type="AglareEventName2">PrimeTimeWithDuration</convert>
	</widget>
</screen>
# 2. Esempio di Converter per NextEventList

<screen name="NextEventListScreen" position="center,center" size="1280,720" title="Next Events">
	<widget name="nextEventList" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="silver" valign="center">
		<convert type="AglareEventName2">NextEventList</convert>
	</widget>
</screen>
# 3. Esempio di Converter per NextEventList2

<screen name="NextEventList2Screen" position="center,center" size="1280,720" title="Next Events 2">
	<widget name="nextEventList2" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="blue" valign="center">
		<convert type="AglareEventName2">NextEventList2</convert>
	</widget>
</screen>
# 4. Esempio di Converter per NextTimeDuration

<screen name="NextTimeDurationScreen" position="center,center" size="1280,720" title="Next Event Time Duration">
	<widget name="nextTimeDuration" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="green" valign="center">
		<convert type="AglareEventName2">NextTimeDuration</convert>
	</widget>
</screen>
# 5. Esempio di Converter per PrimeTimeNoDuration

<screen name="PrimeTimeNoDurationScreen" position="center,center" size="1280,720" title="Prime Time No Duration">
	<widget name="primeTimeNoDuration" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 26" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="red" valign="center">
		<convert type="AglareEventName2">PrimeTimeNoDuration</convert>
	</widget>
</screen>
# 6. Esempio di Converter per NextNameNext

<screen name="NextNameNextScreen" position="center,center" size="1280,720" title="Next Name Next">
	<widget name="nextNameNext" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="purple" valign="center">
		<convert type="AglareEventName2">NextNameNext</convert>
	</widget>
</screen>
# 7. Esempio di Converter per FullDescription

<screen name="FullDescriptionScreen" position="center,center" size="1280,720" title="Full Event Description">
	<widget name="fullDescription" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="orange" valign="center">
		<convert type="AglareEventName2">FullDescription</convert>
	</widget>
</screen>
# 8. Esempio di Converter per NextNameWithOutTime

<screen name="NextNameWithoutTimeScreen" position="center,center" size="1280,720" title="Next Name Without Time">
	<widget name="nextNameWithoutTime" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="yellow" valign="center">
		<convert type="AglareEventName2">NextNameWithOutTime</convert>
	</widget>
</screen>
# 9. Esempio di Converter per ID

<screen name="EventIDScreen" position="center,center" size="1280,720" title="Event ID">
	<widget name="eventID" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="cyan" valign="center">
		<convert type="AglareEventName2">ID</convert>
	</widget>
</screen>
# 10. Esempio di Converter per NextDescription

<screen name="NextDescriptionScreen" position="center,center" size="1280,720" title="Next Event Description">
	<widget name="nextDescription" source="ServiceEvent" render="Label" position="50,50" size="1180,50" font="Bold; 24" backgroundColor="background" transparent="1" noWrap="1" zPosition="1" foregroundColor="magenta" valign="center">
		<convert type="AglareEventName2">NextDescription</convert>
	</widget>
</screen>
"""
