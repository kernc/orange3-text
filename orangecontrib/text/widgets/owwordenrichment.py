from PyQt4 import QtGui
import numpy as np

from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.widget import OWWidget
from Orange.data import Table
from orangecontrib.text.stats import false_discovery_rate, hypergeom_p_values


class OWWordEnrichment(OWWidget):
    # Basic widget info
    name = "Word Enrichment"
    description = "Word enrichment analysis for selected documents."
    icon = "icons/SetEnrichment.svg"
    priority = 60

    # Input/output
    inputs = [("Selected Data", Table, "set_data_selected"),
              ("Other Data", Table, "set_data_other")]
    want_main_area = True

    # Settings
    filter_by_p = Setting(False)
    filter_p_value = Setting(0.01)
    filter_by_fdr = Setting(True)
    filter_fdr_value = Setting(0.2)

    def __init__(self):
        super().__init__()

        # Init data
        self.selected_data = None
        self.other_data = None
        self.words = []
        self.p_values = []
        self.fdr_values = []

        # Info section
        fbox = gui.widgetBox(self.controlArea, "Info")
        self.info_all = gui.label(fbox, self, 'Cluster words:')
        self.info_sel = gui.label(fbox, self, 'Selected words:')
        self.info_fil = gui.label(fbox, self, 'After filtering:')

        # Filtering settings
        fbox = gui.widgetBox(self.controlArea, "Filter")
        hbox = gui.widgetBox(fbox, orientation=0)

        self.chb_p = gui.checkBox(hbox, self, "filter_by_p", "p-value",
                                  callback=self.filter_and_display,
                                  tooltip="Filter by word p-value")
        self.spin_p = gui.doubleSpin(hbox, self, 'filter_p_value',
                                     1e-4, 1, step=1e-4, labelWidth=15,
                                     callback=self.filter_and_display,
                                     callbackOnReturn=True,
                                     tooltip="Max p-value for word")
        self.spin_p.setEnabled(self.filter_by_p)

        hbox = gui.widgetBox(fbox, orientation=0)
        self.chb_fdr = gui.checkBox(hbox, self, "filter_by_fdr", "FDR",
                                    callback=self.filter_and_display,
                                    tooltip="Filter by word FDR")
        self.spin_fdr = gui.doubleSpin(hbox, self, 'filter_fdr_value',
                                       1e-4, 1, step=1e-4, labelWidth=15,
                                       callback=self.filter_and_display,
                                       callbackOnReturn=True,
                                       tooltip="Max p-value for word")
        self.spin_fdr.setEnabled(self.filter_by_fdr)
        gui.rubber(self.controlArea)

        # Word's list view
        self.cols = ['Word', 'p-value', 'FDR']
        self.sig_words = QtGui.QTreeWidget()
        self.sig_words.setColumnCount(len(self.cols))
        self.sig_words.setHeaderLabels(self.cols)
        self.sig_words.setSortingEnabled(True)
        self.sig_words.setSelectionMode(QtGui.QTreeView.ExtendedSelection)
        self.sig_words.sortByColumn(2, 0)   # 0 is ascending order
        for i in range(len(self.cols)):
            self.sig_words.resizeColumnToContents(i)
        self.mainArea.layout().addWidget(self.sig_words)

    def set_data_selected(self, data=None):
        self.selected_data = data

    def set_data_other(self, data=None):
        self.other_data = data

    def handleNewSignals(self):
        self.check_data()

    def check_data(self):
        self.error(1)
        if isinstance(self.selected_data, Table) and \
                isinstance(self.other_data, Table):
            if self.selected_data.domain == self.other_data.domain:
                self.apply()
            else:
                self.clear()
                self.error(1, 'The domains do not match')
        else:
            self.clear()

    def clear(self):
        self.sig_words.clear()
        self.info_all.setText('Cluster words:')
        self.info_sel.setText('Selected words:')
        self.info_fil.setText('After filtering:')

    def filter_enabled(self, b):
        self.chb_p.setEnabled(b)
        self.chb_fdr.setEnabled(b)
        self.spin_p.setEnabled(b)
        self.spin_fdr.setEnabled(b)

    def filter_and_display(self):
        self.spin_p.setEnabled(self.filter_by_p)
        self.spin_fdr.setEnabled(self.filter_by_fdr)
        self.sig_words.clear()
        count = 0
        if self.words:
            for word, pval, fval in zip(self.words, self.p_values, self.fdr_values):
                if (not self.filter_by_p or pval <= self.filter_p_value) and \
                        (not self.filter_by_fdr or fval <= self.filter_fdr_value):
                    it = EATreeWidgetItem(word, pval, fval, self.sig_words)
                    self.sig_words.addTopLevelItem(it)
                    count += 1

        for i in range(len(self.cols)):
            self.sig_words.resizeColumnToContents(i)

        self.info_all.setText('Cluster words: {}'.format(len(self.selected_data.domain.attributes)))
        self.info_sel.setText('Selected words: {}'.format(np.count_nonzero(np.sum(self.selected_data.X, axis=0))))
        if not self.filter_by_p and not self.filter_by_fdr:
            self.info_fil.setText('After filtering:')
            self.info_fil.setEnabled(False)
        else:
            self.info_fil.setEnabled(True)
            self.info_fil.setText('After filtering: {}'.format(count))

    def progress(self, p):
        self.progressBarSet(p)

    def apply(self):
        if self.selected_data.X.size > 0:
            self.progressBarInit()
            self.clear()
            self.filter_enabled(False)

            self.words = [i.name for i in self.selected_data.domain.attributes]
            self.p_values = hypergeom_p_values(self.selected_data.X,
                                               self.other_data.X,
                                               callback=self.progress)
            self.fdr_values = false_discovery_rate(self.p_values)
            self.filter_and_display()
            self.filter_enabled(True)
            self.progressBarFinished()
        else:
            self.clear()


fp = lambda score: "%0.5f" % score if score > 10e-3 else "%0.1e" % score
fpt = lambda score: "%0.9f" % score if score > 10e-3 else "%0.5e" % score


class EATreeWidgetItem(QtGui.QTreeWidgetItem):
    def __init__(self, word, p_value, f_value, parent):
        super().__init__(parent)
        self.data = [word, p_value, f_value]
        self.setText(0, word)
        self.setText(1, fp(p_value))
        self.setToolTip(1, fpt(p_value))
        self.setText(2, fp(f_value))
        self.setToolTip(2, fpt(f_value))

    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        return self.data[col] < other.data[col]
