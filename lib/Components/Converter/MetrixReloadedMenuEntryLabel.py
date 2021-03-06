from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.config import config
from Poll import Poll

class MetrixReloadedMenuEntryLabel(Poll,Converter,object):
	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		self.poll_interval = 1000
		self.poll_enabled = True
		self.type = str(type)

	def selChanged(self):
		self.downstream_elements.changed((self.CHANGED_ALL, 0))

	@cached
	def getText(self):
		cur = self.source.current
		if cur and len(cur) > 2:
			selectedMenu = cur[2]

		showMenuEntryNames = False
		try:
			showMenuEntryNames = config.plugins.MetrixReloaded.showMenuEntryNames.value
		except Exception as e:
			pass		
		
		if(showMenuEntryNames):
			return selectedMenu
		else:
			return ''
	
	text = property(getText)

	def changed(self, what):
		if what[0] == self.CHANGED_DEFAULT:
			self.source.onSelectionChanged.append(self.selChanged)		
		Converter.changed(self, what)

		