#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import division
#
# Extended ServiceName Converter for Enigma2 Dreamboxes (ServiceName2.py)
# Coded by vlamo (c) 2011
#
# Version: 0.4 (03.06.2011 18:40)
# Version: 0.5 (08.09.2012) add Alternative numbering mode support - Dmitry73 & 2boom
# Version: 0.6 (19.10.2012) add stream mapping
# Version: 0.7 (19.09.2013) add iptv info - nikolasi & 2boom
# Version: 0.8 (29.10.2013) add correct output channelnumner - Dmitry73
# Version: 0.9 (18.11.2013) code fix and optimization - Taapat & nikolasi
# Version: 1.0 (04.12.2013) code fix and optimization - Dmitry73
# Version: 1.1 (06-17.12.2013) small cosmetic fix - 2boom
# Version: 1.2 (25.12.2013) small iptv fix - MegAndretH
# Version: 1.3 (27.01.2014) small iptv fix - 2boom
# Version: 1.4 (30.06.2014) fix iptv reference - 2boom
# Version: 1.5 (04.07.2014) fix iptv reference cosmetic - 2boom
# Version: 1.6 (14.10.2014) add Tricolor Sibir prov - 2boom
# Version: 1.7 (10.03.2015) remove Tricolor Sibir prov - 2boom
# Version: 1.8 (15.03.2015) add custom provname - 2boom
# Version: 1.9 (31.07.2015) add custom provname for custom name channel- 2boom
# Version: 2.0 (11.12.2018) Edit to compitable with OE2.0 and OE2.5 - RAED
# Version: 2.1 (21.05.2021) Support py3 - RAED
# 2025.04.01 @ lululla fix

from Components.Converter.Converter import Converter
from enigma import (
	iServiceInformation,
	iPlayableService,
	iPlayableServicePtr,
	eServiceReference,
	eServiceCenter,
	eTimer,
	getBestPlayableServiceReference,
	iDVBFrontend,
)
from Components.Element import cached
from Components.config import config
import NavigationInstance
from os import path as os_path

import gettext
_ = gettext.gettext


def DreamOS():
	if os_path.exists('/var/lib/dpkg/status'):
		return DreamOS


class AglareServName2(Converter, object):
	NAME = 0
	NUMBER = 1
	BOUQUET = 2
	PROVIDER = 3
	REFERENCE = 4
	ORBPOS = 5
	TPRDATA = 6
	SATELLITE = 7
	ALLREFERENCE = 8
	FORMAT = 9

	def __init__(self, type):
		Converter.__init__(self, type)
		if type == "Name" or not len(str(type)):
			self.type = self.NAME
		elif type == "Number":
			self.type = self.NUMBER
		elif type == "Bouquet":
			self.type = self.BOUQUET
		elif type == "Provider":
			self.type = self.PROVIDER
		elif type == "Reference":
			self.type = self.REFERENCE
		elif type == "OrbitalPos":
			self.type = self.ORBPOS
		elif type == "TransponderInfo":
			self.type = self.TPRDATA
		elif type == "Satellite":
			self.type = self.SATELLITE
		elif type == "AllReference":
			self.type = self.ALLREFERENCE
		else:
			self.type = self.FORMAT
			self.sfmt = type[:]

		self.refstr = self.isStream = self.ref = self.info = self.what = self.tpdata = None
		self.timer = eTimer()
		try:
			self.timer.callback.append(self.neededChange)
		except:
			self.timer_conn = self.timer.timeout.connect(self.neededChange)

	def getServiceNumber(self, ref):
		def searchHelper(serviceHandler, num, bouquet):
			servicelist = serviceHandler.list(bouquet)
			if servicelist is not None:
				while True:
					s = servicelist.getNext()
					if not s.valid():
						break
					if not (s.flags & (eServiceReference.isMarker | eServiceReference.isDirectory)):
						num += 1
						if s == ref:
							return s, num
			return None, num

		if isinstance(ref, eServiceReference):
			isRadioService = ref.getData(0) in (2, 10)
			lastpath = isRadioService and config.radio.lastroot.value or config.tv.lastroot.value
			if 'FROM BOUQUET' not in lastpath:
				if 'FROM PROVIDERS' in lastpath:
					return 'P', 'Provider'
				if 'FROM SATELLITES' in lastpath:
					return 'S', 'Satellites'
				if ') ORDER BY name' in lastpath:
					return 'A', 'All Services'
				return 0, 'N/A'
			try:
				acount = config.plugins.NumberZapExt.enable.value and config.plugins.NumberZapExt.acount.value or config.usage.alternative_number_mode.value
			except:
				acount = False
			rootstr = ''
			for x in lastpath.split(';'):
				if x != '':
					rootstr = x
			serviceHandler = eServiceCenter.getInstance()
			if acount is True or not config.usage.multibouquet.value:
				bouquet = eServiceReference(rootstr)
				service, number = searchHelper(serviceHandler, 0, bouquet)
			else:
				if isRadioService:
					bqrootstr = '1:7:2:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.radio" ORDER BY bouquet'
				else:
					bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
				number = 0
				cur = eServiceReference(rootstr)
				bouquet = eServiceReference(bqrootstr)
				bouquetlist = serviceHandler.list(bouquet)
				if bouquetlist is not None:
					while True:
						bouquet = bouquetlist.getNext()
						if not bouquet.valid():
							break
						if bouquet.flags & eServiceReference.isDirectory:
							service, number = searchHelper(serviceHandler, number, bouquet)
							if service is not None and cur == bouquet:
								break
			if service is not None:
				info = serviceHandler.info(bouquet)
				name = info and info.getName(bouquet) or ''
				return number, name
		return 0, ''

	def getProviderName(self, ref):
		if isinstance(ref, eServiceReference):
			from Screens.ChannelSelection import service_types_radio, service_types_tv
			typestr = ref.getData(0) in (2, 10) and service_types_radio or service_types_tv
			pos = typestr.rfind(':')
			rootstr = '%s (channelID == %08x%04x%04x) && %s FROM PROVIDERS ORDER BY name' % (typestr[:pos + 1], ref.getUnsignedData(4), ref.getUnsignedData(2), ref.getUnsignedData(3), typestr[pos + 1:])
			provider_root = eServiceReference(rootstr)
			serviceHandler = eServiceCenter.getInstance()
			providerlist = serviceHandler.list(provider_root)
			if providerlist is not None:
				while True:
					provider = providerlist.getNext()
					if not provider.valid():
						break
					if provider.flags & eServiceReference.isDirectory:
						servicelist = serviceHandler.list(provider)
						if servicelist is not None:
							while True:
								service = servicelist.getNext()
								if not service.valid():
									break
								if service == ref:
									info = serviceHandler.info(provider)
									return info and info.getName(provider) or "Unknown"
		return ""

	def getTransponderInfo(self, info, ref, fmt):
		result = ""
		if self.tpdata is None:
			if ref:
				self.tpdata = ref and info.getInfoObject(ref, iServiceInformation.sTransponderData)
			else:
				self.tpdata = info.getInfoObject(iServiceInformation.sTransponderData)
			if not isinstance(self.tpdata, dict):
				self.tpdata = None
				return result
		if self.isStream:
			type = 'IP-TV'
		else:
			type = self.tpdata.get('tuner_type', '')
		if not fmt or fmt == 'T':
			if DreamOS():
				if type == iDVBFrontend.feCable:
					fmt = ["t ", "F ", "Y ", "i ", "f ", "M"]  # (type frequency symbol_rate inversion fec modulation)
				elif type == iDVBFrontend.feTerrestrial:
					if ref:
						fmt = ["O ", "F ", "c ", "l ", "h ", "m ", "g "]   # (orbital_position code_rate_hp transmission_mode guard_interval constellation)
					else:
						fmt = ["t ", "F ", "c ", "l ", "h ", "m ", "g "]   # (type frequency code_rate_hp transmission_mode guard_interval constellation)
				elif type == 'IP-TV':
					return _("Streaming")
				else:
					fmt = ["O ", "F", "p ", "Y ", "f"]
			else:
				if type == 'DVB-C':
					fmt = ["t ", "F ", "Y ", "i ", "f ", "M"]  # (type frequency symbol_rate inversion fec modulation)
				elif type == 'DVB-T':
					if ref:
						fmt = ["O ", "F ", "c ", "l ", "h ", "m ", "g "]   # (orbital_position code_rate_hp transmission_mode guard_interval constellation)
					else:
						fmt = ["t ", "F ", "c ", "l ", "h ", "m ", "g "]   # (type frequency code_rate_hp transmission_mode guard_interval constellation)
				elif type == 'IP-TV':
					return _("Streaming")
				else:
					fmt = ["O ", "F", "p ", "Y ", "f"]
		for line in fmt:
			f = line[:1]
			if f == 't':  # %t - tuner_type (dvb-s/s2/c/t)
				if DreamOS():
					if type == iDVBFrontend.feSatellite:
						result += _("Satellite")
					elif type == iDVBFrontend.feCable:
						result += _("Cable")
					elif type == iDVBFrontend.feTerrestrial:
						result += _("Terrestrial")
					elif type == 'IP-TV':
						result += _('Stream-tv')
					else:
						result += 'N/A'
				else:
					if type == 'DVB-S':
						result += _("Satellite")
					elif type == 'DVB-C':
						result += _("Cable")
					elif type == 'DVB-T':
						result += _("Terrestrial")
					elif type == 'IP-TV':
						result += _('Stream-tv')
					else:
						result += 'N/A'
			elif f == 's':  # %s - system (dvb-s/s2/c/t)
				if DreamOS():
					if type == iDVBFrontend.feSatellite:
						x = self.tpdata.get('system', 0)
						result += x in list(range(2)) and {0: 'DVB-S', 1: 'DVB-S2'}[x] or ''
					else:
						result += 'N/A'  # str(type)
				else:
					if type == 'DVB-S':
						x = self.tpdata.get('system', 0)
						result += x in list(range(2)) and {0: 'DVB-S', 1: 'DVB-S2'}[x] or ''
					else:
						result += 'N/A'
			elif f == 'F':  # %F - frequency (dvb-s/s2/c/t) in KHz
				if DreamOS():
					result += '%d' % (self.tpdata.get('frequency', 0) / 1000)
				else:
					if type in ('DVB-S', 'DVB-C') and self.tpdata.get('frequency', 0) > 0:
						result += '%d MHz' % (self.tpdata.get('frequency', 0) / 1000)
					if type in ('DVB-T'):
						result += '%.3f MHz' % (((self.tpdata.get('frequency', 0) + 500) / 1000) / 1000.0)
						# result += '%.3f'%(((self.tpdata.get('frequency', 0) / 1000) +1) / 1000.0) + " MHz "
			elif f == 'f':  # %f - fec_inner (dvb-s/s2/c/t)
				if DreamOS():
					if type == iDVBFrontend.feCable or type == iDVBFrontend.feSatellite:
						x = self.tpdata.get('fec_inner', 15)
						result += x in list(range(10)) + [15] and {0: 'Auto', 1: '1/2', 2: '2/3', 3: '3/4', 4: '5/6', 5: '7/8', 6: '8/9', 7: '3/5', 8: '4/5', 9: '9/10', 15: 'None'}[x] or ''
					elif type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('code_rate_lp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
				else:
					if type in ('DVB-S', 'DVB-C'):
						x = self.tpdata.get('fec_inner', 15)
						result += x in list(range(10)) + [15] and {0: 'Auto', 1: '1/2', 2: '2/3', 3: '3/4', 4: '5/6', 5: '7/8', 6: '8/9', 7: '3/5', 8: '4/5', 9: '9/10', 15: 'None'}[x] or ''
					elif type == 'DVB-T':
						x = self.tpdata.get('code_rate_lp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
			elif f == 'i':  # %i - inversion (dvb-s/s2/c/t)
				if DreamOS():
					x = self.tpdata.get('inversion', 2)
					result += x in list(range(3)) and {0: 'On', 1: 'Off', 2: 'Auto'}[x] or ''
				else:
					if type in ('DVB-S', 'DVB-C', 'DVB-T'):
						x = self.tpdata.get('inversion', 2)
						result += x in list(range(3)) and {0: 'On', 1: 'Off', 2: 'Auto'}[x] or ''
			elif f == 'O':  # %O - orbital_position (dvb-s/s2)
				if DreamOS():
					if type == iDVBFrontend.feSatellite:
						x = self.tpdata.get('orbital_position', 0)
						result += x > 1800 and "%d.%d°W" % ((3600 - x) / 10, (3600 - x) % 10) or "%d.%d°E" % (x / 10, x % 10)
						result = result.replace("°", "")
					elif type == 'Iptv':
						result += 'Stream'
				else:
					if type == 'DVB-S':
						x = self.tpdata.get('orbital_position', 0)
						result += x > 1800 and "%d.%d°W" % ((3600 - x) / 10, (3600 - x) % 10) or "%d.%d°E" % (x / 10, x % 10)
						result = result.replace("°", "")
					elif type == 'DVB-T':
						result += 'DVB-T'
					elif type == 'DVB-C':
						result += 'DVB-C'
					elif type == 'Iptv':
						result += 'Stream'
			elif f == 'M':  # %M - modulation (dvb-s/s2/c)
				if DreamOS():
					x = self.tpdata.get('modulation', 1)
					if type == iDVBFrontend.feSatellite:
						result += x in list(range(4)) and {0: 'Auto', 1: 'QPSK', 2: '8PSK', 3: 'QAM16'}[x] or ''
					elif type == iDVBFrontend.feCable:
						result += x in list(range(6)) and {0: 'Auto', 1: 'QAM16', 2: 'QAM32', 3: 'QAM64', 4: 'QAM128', 5: 'QAM256'}[x] or ''
				else:
					x = self.tpdata.get('modulation', 1)
					if type == 'DVB-S':
						result += x in list(range(4)) and {0: 'Auto', 1: 'QPSK', 2: '8PSK', 3: 'QAM16'}[x] or ''
					elif type == 'DVB-C':
						result += x in list(range(6)) and {0: 'Auto', 1: 'QAM16', 2: 'QAM32', 3: 'QAM64', 4: 'QAM128', 5: 'QAM256'}[x] or ''
			elif f == 'p':  # %p - polarization (dvb-s/s2)
				if DreamOS():
					if type == iDVBFrontend.feSatellite:
						x = self.tpdata.get('polarization', 0)
						result += x in list(range(4)) and {0: 'H', 1: 'V', 2: 'L', 3: 'R'}[x] or '?'
				else:
					if type == 'DVB-S':
						x = self.tpdata.get('polarization', 0)
						result += x in list(range(4)) and {0: 'H', 1: 'V', 2: 'L', 3: 'R'}[x] or '?'
			elif f == 'Y':  # %Y - symbol_rate (dvb-s/s2/c)
				if DreamOS():
					if type == iDVBFrontend.feCable or type == iDVBFrontend.feSatellite:
						result += '%d' % (self.tpdata.get('symbol_rate', 0) / 1000)
				else:
					if type in ('DVB-C', 'DVB-S'):
						result += '%d' % (self.tpdata.get('symbol_rate', 0) / 1000)
			elif f == 'r':  # %r - rolloff (dvb-s2)
				if not self.isStream:
					x = self.tpdata.get('rolloff')
					if x is not None:
						result += x in list(range(3)) and {0: '0.35', 1: '0.25', 2: '0.20'}[x] or ''
			elif f == 'o':  # %o - pilot (dvb-s2)
				if not self.isStream:
					x = self.tpdata.get('pilot')
					if x is not None:
						result += x in list(range(3)) and {0: 'Off', 1: 'On', 2: 'Auto'}[x] or ''
			elif f == 'c':  # %c - constellation (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('constellation', 3)
						result += x in list(range(4)) and {0: 'QPSK', 1: 'QAM16', 2: 'QAM64', 3: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('constellation', 3)
						result += x in list(range(4)) and {0: 'QPSK', 1: 'QAM16', 2: 'QAM64', 3: 'Auto'}[x] or ''
			elif f == 'l':  # %l - code_rate_lp (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('code_rate_lp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('code_rate_lp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
			elif f == 'h':  # %h - code_rate_hp (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('code_rate_hp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('code_rate_hp', 5)
						result += x in list(range(6)) and {0: '1/2', 1: '2/3', 2: '3/4', 3: '5/6', 4: '7/8', 5: 'Auto'}[x] or ''
			elif f == 'm':  # %m - transmission_mode (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('transmission_mode', 2)
						result += x in list(range(3)) and {0: '2k', 1: '8k', 2: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('transmission_mode', 2)
						result += x in list(range(3)) and {0: '2k', 1: '8k', 2: 'Auto'}[x] or ''
			elif f == 'g':  # %g - guard_interval (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('guard_interval', 4)
						result += x in list(range(5)) and {0: '1/32', 1: '1/16', 2: '1/8', 3: '1/4', 4: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('guard_interval', 4)
						result += x in list(range(5)) and {0: '1/32', 1: '1/16', 2: '1/8', 3: '1/4', 4: 'Auto'}[x] or ''
			elif f == 'b':  # %b - bandwidth (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('bandwidth', 1)
						result += x in list(range(4)) and {0: '8 MHz', 1: '7 MHz', 2: '6 MHz', 3: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('bandwidth', 1)
						result += x in list(range(4)) and {0: '8 MHz', 1: '7 MHz', 2: '6 MHz', 3: 'Auto'}[x] or ''
			elif f == 'e':  # %e - hierarchy_information (dvb-t)
				if DreamOS():
					if type == iDVBFrontend.feTerrestrial:
						x = self.tpdata.get('hierarchy_information', 4)
						result += x in list(range(5)) and {0: 'None', 1: '1', 2: '2', 3: '4', 4: 'Auto'}[x] or ''
				else:
					if type == 'DVB-T':
						x = self.tpdata.get('hierarchy_information', 4)
						result += x in list(range(5)) and {0: 'None', 1: '1', 2: '2', 3: '4', 4: 'Auto'}[x] or ''
			result += line[1:]
		return result

	def getSatelliteName(self, ref):
		if isinstance(ref, eServiceReference):
			orbpos = ref.getUnsignedData(4) >> 16
			if orbpos == 0xFFFF:  # Cable
				return _("Cable")
			elif orbpos == 0xEEEE:  # Terrestrial
				return _("Terrestrial")
			else:  # Satellite
				orbpos = ref.getData(4) >> 16
				if orbpos < 0:
					orbpos += 3600
				try:
					from Components.NimManager import nimmanager
					return str(nimmanager.getSatDescription(orbpos))
				except:
					dir = ref.flags & (eServiceReference.isDirectory | eServiceReference.isMarker)
					if not dir:
						refString = ref.toString().lower()
						if refString.startswith("-1"):
							return ''
						elif refString.startswith("1:134:"):
							return _("Alternative")
						elif refString.startswith("4097:"):
							return _("Internet")
						else:
							return orbpos > 1800 and "%d.%d°W" % ((3600 - orbpos) / 10, (3600 - orbpos) % 10) or "%d.%d°E" % (orbpos / 10, orbpos % 10)
		return ""

	def getIPTVProvider(self, refstr):
		if '3a10000' in refstr or ('::' in refstr and '2' == refstr.split(':')[-3]):
			return "Farline"
		elif '3a24000' in refstr or ('::' in refstr and '2' == refstr.split(':')[-3]):
			return "SHARA IPTV"
		return ""

	def getPlayingref(self, ref):
		playingref = None
		if NavigationInstance.instance:
			playingref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
		if not playingref:
			playingref = eServiceReference()
		return playingref

	def resolveAlternate(self, ref):
		nref = getBestPlayableServiceReference(ref, self.getPlayingref(ref))
		if not nref:
			nref = getBestPlayableServiceReference(ref, eServiceReference(), True)
		return nref

	def getReferenceType(self, refstr, ref):
		if ref is None:
			if NavigationInstance.instance:
				playref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
				if playref:
					refstr = playref.toString() or ''
					prefix = ''
					if refstr.startswith("4097:"):
						prefix += "GStreamer "
					if '%3a//' in refstr:
						sref = ' '.join(refstr.split(':')[10:])
						refstr = prefix + sref
					else:
						sref = ':'.join(refstr.split(':')[:10])
						refstr = prefix + sref
		else:
			if refstr != '':
				prefix = ''
				if refstr.startswith("1:7:"):
					if 'FROM BOUQUET' in refstr:
						prefix += "Bouquet "
					elif '(provider == ' in refstr:
						prefix += "Provider "
					elif '(satellitePosition == ' in refstr:
						prefix += "Satellit "
					elif '(channelID == ' in refstr:
						prefix += "Current tr "
				elif refstr.startswith("1:134:"):
					prefix += "Alter "
				elif refstr.startswith("1:64:"):
					prefix += "Marker "
				elif refstr.startswith("4097:"):
					prefix += "GStreamer "
				if self.isStream:
					if self.refstr:
						if '%3a//' in self.refstr:
							sref = ' '.join(self.refstr.split(':')[10:])
						else:
							sref = ':'.join(self.refstr.split(':')[:10])
					else:
						sref = ' '.join(refstr.split(':')[10:])
					return prefix + sref
				else:
					if self.refstr:
						sref = ':'.join(self.refstr.split(':')[:10])
					else:
						sref = ':'.join(refstr.split(':')[:10])
					return prefix + sref
		return refstr

	@cached
	def getText(self):
		service = self.source.service
		if isinstance(service, iPlayableServicePtr):
			info = service and service.info()
			ref = None
		else:  # reference
			info = service and self.source.info
			ref = service
		if not info:
			return ""
		refname = 'ServiceName2.ref'
		searchpath = ['/etc/enigma2/']
		if ref:
			refstr = ref.toString()
		else:
			refstr = info.getInfoString(iServiceInformation.sServiceref)
		if refstr is None:
			refstr = ''
		if self.type == self.NAME:
			name = ref and (info.getName(ref) or 'N/A') or (info.getName() or 'N/A')
			prefix = ''
			if self.ref:
				prefix = " (alter)"
			name += prefix
			return name.replace('\xc2\x86', '').replace('\xc2\x87', '')
		elif self.type == self.NUMBER:
			try:
				service = self.source.serviceref
				num = service and service.getChannelNum() or None
			except:
				num = None
			if num:
				return str(num)
			else:
				num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
				return num and str(num) or ''
		elif self.type == self.BOUQUET:
			num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
			return bouq
		elif self.type == self.PROVIDER:
			tmpprov = tmpref = refpath = ''
			if self.isStream:
				if self.refstr:
					tmpprov = self.getIPTVProvider(self.refstr)
				tmpprov = self.getIPTVProvider(refstr)
			else:
				if self.ref:
					tmpprov = self.getProviderName(self.ref)
				if ref:
					tmpprov = self.getProviderName(ref)
				else:
					tmpprov = info.getInfoString(iServiceInformation.sProvider) or ''
			if tmpprov == '' or 'Unknown' in tmpprov:
				if self.refstr:
					tmpref = self.refstr
				else:
					tmpref = refstr
				for i in list(range(len(searchpath))):
					if os_path.isfile('%s%s' % (searchpath[i], refname)):
						refpath = '%s%s' % (searchpath[i], refname)
				if refpath != '':
					for line in open(refpath):
						if tmpref in line or tmpref.strip()[:-15] in line:
							tmpprov = line.split(':')[-1].strip('\r').strip('\n').strip()
						# elif line.split()[0][i + 1:] in line:
							# tmpprov = line.split(':')[-1].strip('\r').strip('\n').strip()

				return tmpprov
			return tmpprov
		elif self.type == self.REFERENCE:
			if self.refstr:
				return self.refstr
			return refstr
		elif self.type == self.ORBPOS:
			if self.isStream:
				return r"00\B0E"
			else:
				if self.ref and self.info:
					return self.getTransponderInfo(self.info, self.ref, 'O')
				return self.getTransponderInfo(info, ref, 'O')
		elif self.type == self.TPRDATA:
			if self.isStream:
				return _("Streaming")
			else:
				if self.ref and self.info:
					return self.getTransponderInfo(self.info, self.ref, 'T')
				return self.getTransponderInfo(info, ref, 'T')
		elif self.type == self.SATELLITE:
			if self.isStream:
				return _("Internet")
			else:
				if self.ref:
					return self.getSatelliteName(self.ref)
			# test
				return self.getSatelliteName(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))

#               elif self.type == self.ALLREF:
#                       tmpref = self.getReferenceType(refstr, ref)
#                       if 'Bouquet' in tmpref or 'Satellit' in tmpref or 'Provider' in tmpref:
#                               return ' '
#                       elif '%3a' in tmpref:
#                               return ':'.join(refstr.split(':')[:10])
#                       return tmpref
		elif self.type == self.ALLREFERENCE:
			orbp = "%s" % (self.getTransponderInfo(info, ref, '%O'))
			refer = "%s" % (ref and ref.toString() or info.getInfoString(iServiceInformation.sServiceref))
			if isinstance(service, iPlayableServicePtr):
				prov = "%s" % (info.getInfoString(iServiceInformation.sProvider))
			else:
				prov = "%s" % (ref and self.getProviderName(ref))
			all = "%s,,,%s,,,%s" % (refer, prov, orbp)
			return all
		elif self.type == self.FORMAT:
			num = bouq = ''
			tmp = self.sfmt[:].split("%")
			if tmp:
				ret = tmp[0]
				tmp.remove(ret)
			else:
				return ""
			for line in tmp:
				f = line[:1]
				if f == 'N':    # %N - Name
					name = ref and (info.getName(ref) or 'N/A') or (info.getName() or 'N/A')
					postfix = ''
					if self.ref:
						postfix = " (alter)"
					name += postfix
					ret += name.replace('\xc2\x86', '').replace('\xc2\x87', '')
				elif f == 'n':  # %n - Number
					try:
						service = self.source.serviceref
						num = service and service.getChannelNum() or None
					except:
						num = None
					if num:
						ret += str(num)
					else:
						num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
						ret += num and str(num) or ''
				elif f == 'B':  # %B - Bouquet
					num, bouq = self.getServiceNumber(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
					ret += bouq
				elif f == 'P':  # %P - Provider
					tmpprov = tmpref = refpath = ''
					if self.isStream:
						if self.refstr:
							tmpprov = self.getIPTVProvider(self.refstr)
						tmpprov = self.getIPTVProvider(refstr)
					else:
						if self.ref:
							tmpprov = self.getProviderName(self.ref)
						if ref:
							tmpprov = self.getProviderName(ref)
						else:
							tmpprov = info.getInfoString(iServiceInformation.sProvider) or ''
					if tmpprov == '' or 'Unknown' in tmpprov:
						if self.refstr:
							tmpref = self.refstr
						else:
							tmpref = refstr
						for i in list(range(len(searchpath))):
							if os_path.isfile('%s%s' % (searchpath[i], refname)):
								refpath = '%s%s' % (searchpath[i], refname)
							if refpath != '':
								for line in open(refpath):
									i = len(line.split(':')[0])
									if tmpref in line or tmpref.strip()[:-15] in line:
										tmpprov = line.split(':')[-1].strip('\r').strip('\n').strip()
					ret += tmpprov
				elif f == 'R':  # %R - Reference
					if self.refstr:
						ret += self.refstr
					else:
						ret += refstr
				elif f == 'S':  # %S - Satellite
					if self.isStream:
						ret += _("Internet")
					else:
						if self.ref:
							ret += self.getSatelliteName(self.ref)
						else:
							ret += self.getSatelliteName(ref or eServiceReference(info.getInfoString(iServiceInformation.sServiceref)))
				elif f == 'A':  # %A - AllRef
					tmpref = self.getReferenceType(refstr, ref)
					if 'Bouquet' in tmpref or 'Satellit' in tmpref or 'Provider' in tmpref:
						ret += ' '
					elif '%3a' in tmpref:
						ret += ':'.join(refstr.split(':')[:10])
					else:
						ret += tmpref
				elif f in 'TtsFfiOMpYroclhmgbe':
					if self.ref:
						ret += self.getTransponderInfo(self.info, self.ref, f)
					else:
						ret += self.getTransponderInfo(info, ref, f)
				ret += line[1:]
			return '%s' % (ret.replace('N/A', '').strip())

	text = property(getText)

	def neededChange(self):
		if self.what:
			Converter.changed(self, self.what)
			self.what = None

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in (iPlayableService.evStart,):
			self.refstr = self.isStream = self.ref = self.info = self.tpdata = None
			if self.type in (self.NUMBER, self.BOUQUET) or \
			   (self.type == self.FORMAT and ('%n' in self.sfmt or '%B' in self.sfmt)):
				self.what = what
				self.timer.start(200, True)
			else:
				Converter.changed(self, what)
