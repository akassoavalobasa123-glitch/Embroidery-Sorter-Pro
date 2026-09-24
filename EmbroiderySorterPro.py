import sys, json, shutil, datetime, urllib.request, urllib.error, tempfile, subprocess, re
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QIcon
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QFileDialog,QFrame,QListWidget,QListWidgetItem,QProgressBar,QMessageBox,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QDialog,QDialogButtonBox,QSystemTrayIcon)

APP_NAME='Embroidery Sorter Pro'
APP_VERSION='2.4.0'
GITHUB_REPO='akassoavalobasa123-glitch/Embroidery-Sorter-Pro'
GITHUB_LATEST_API='https://api.github.com/repos/akassoavalobasa123-glitch/Embroidery-Sorter-Pro/releases/latest'DEFAULT_PROTECTED=['.png','.emf','.pdf','.txt']
ACTIONS=['Move to matching folder','Keep','Safe Trash (undoable)','Recycle Bin','Ignore','Auto']

def now(): return datetime.datetime.now().isoformat(timespec='seconds')
def norm_ext(s):
    s=s.strip().lower()
    return s if s.startswith('.') else ('.'+s if s else '')

def make_icon():
    pix=QPixmap(64,64); pix.fill(Qt.transparent); p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing); p.setBrush(QColor('#111111')); p.setPen(Qt.NoPen); p.drawRoundedRect(2,2,60,60,15,15); p.setBrush(QColor('#F5B942')); p.drawRoundedRect(12,20,40,30,5,5); p.drawRoundedRect(13,15,17,10,4,4); p.end(); return QIcon(pix)

def default_rules(): return {e:{'action':'Keep'} for e in DEFAULT_PROTECTED}
class UpdateWorker(QThread):
    finished=Signal(object)
    def run(self):
        try:
            req=urllib.request.Request(GITHUB_LATEST_API, headers={'User-Agent':'EmbroiderySorterPro-Updater','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data=json.loads(r.read().decode('utf-8'))
            tag=str(data.get('tag_name','')).strip()
            latest=tag.lstrip('vV')
            notes=str(data.get('body','')).strip()
            if not latest:
                self.finished.emit({'ok':False,'message':'GitHub release version was not found.'}); return
            def ver(v):
                nums=re.findall(r'\d+', v)
                return tuple(int(x) for x in nums[:3]) if nums else (0,0,0)
            if ver(latest) <= ver(APP_VERSION):
                self.finished.emit({'ok':True,'update':False,'version':latest}); return
            installer=None
            for asset in data.get('assets',[]):
                if str(asset.get('name','')).lower()=='embroidery_sorter_pro_setup.exe':
                    installer=asset.get('browser_download_url'); break
            if not installer:
                installer=f'https://github.com/{GITHUB_REPO}/releases/latest/download/Embroidery_Sorter_Pro_Setup.exe'
            self.finished.emit({'ok':True,'update':True,'version':latest,'url':installer,'notes':notes})
        except Exception as e:
            self.finished.emit({'ok':False,'message':str(e)})

class ScanWorker(QThread):
    done=Signal(object); failed=Signal(str)
    def __init__(self,root,rules): super().__init__(); self.root=Path(root); self.rules=rules
    def run(self):
        try:
            folders={p.name.lower():p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith('.')}
            rows=[]
            for p in self.root.iterdir():
                if not p.is_file() or p.name.startswith('.'): continue
                ext=p.suffix.lower(); rule=self.rules.get(ext,{'action':'Auto'}); action=rule.get('action','Auto'); target=None
                if action=='Auto':
                    target=folders.get(ext[1:].lower()); action='Move to matching folder' if target else 'Safe Trash (undoable)'
                elif action=='Move to matching folder':
                    target=folders.get(rule.get('folder',ext[1:]).lower())
                    if target is None: action='Safe Trash (undoable)'
                rows.append((p,action,target))
            self.done.emit(rows)
        except Exception as e: self.failed.emit(str(e))

class SortWorker(QThread):
    progress=Signal(int,str); done=Signal(object); failed=Signal(str)
    def __init__(self,rows,root): super().__init__(); self.rows=rows; self.root=Path(root)
    def run(self):
        ops=[]; counts={'moved':0,'kept':0,'trashed':0,'recycled':0,'ignored':0,'skipped':0}
        try:
            safe=self.root/'.EmbroiderySorter_Trash'; safe.mkdir(exist_ok=True); total=max(1,len(self.rows))
            for i,(p,action,target) in enumerate(self.rows,1):
                try:
                    if action=='Move to matching folder':
                        dest=target/p.name
                        if dest.exists(): counts['skipped']+=1
                        else: shutil.move(str(p),str(dest)); ops.append({'type':'move','src':str(p),'dest':str(dest)}); counts['moved']+=1
                    elif action=='Safe Trash (undoable)':
                        stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'); dest=safe/f'{stamp}__{p.name}'; shutil.move(str(p),str(dest)); ops.append({'type':'trash','src':str(p),'dest':str(dest)}); counts['trashed']+=1
                    elif action=='Recycle Bin':
                        from send2trash import send2trash; send2trash(str(p)); counts['recycled']+=1
                    elif action=='Keep': counts['kept']+=1
                    else: counts['ignored']+=1
                except Exception: counts['skipped']+=1
                self.progress.emit(int(i*100/total),f'{action}: {p.name}')
            self.done.emit({'counts':counts,'ops':ops})
        except Exception as e: self.failed.emit(str(e))

class DropLineEdit(QLineEdit):
    folderDropped=Signal(str)
    def __init__(self): super().__init__(); self.setAcceptDrops(True)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e):
        for u in e.mimeData().urls():
            p=Path(u.toLocalFile())
            if p.is_dir(): self.setText(str(p)); self.folderDropped.emit(str(p)); break

class RulesDialog(QDialog):
    changed=Signal(object)
    def __init__(self,parent,rules):
        super().__init__(parent); self.setWindowTitle('Rules & Automation'); self.resize(760,500); self.rules={k:dict(v) for k,v in rules.items()}; lay=QVBoxLayout(self)
        info=QLabel("Define exactly what happens to each extension. Auto uses a same-named folder when it exists."); info.setObjectName('Info'); info.setWordWrap(True); lay.addWidget(info)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Extension','Action','Destination folder']); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); lay.addWidget(self.table)
        bbx=QHBoxLayout(); add=QPushButton('+ Add rule'); rem=QPushButton('Remove selected'); add.clicked.connect(self.add_row); rem.clicked.connect(self.remove_row); bbx.addWidget(add); bbx.addWidget(rem); bbx.addStretch(); lay.addLayout(bbx)
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); bb.accepted.connect(self.save); bb.rejected.connect(self.reject); lay.addWidget(bb)
        for ext,rule in sorted(self.rules.items()): self.add_row(ext,rule.get('action','Keep'),rule.get('folder',''))
    def add_row(self,ext='',action='Keep',folder=''):
        r=self.table.rowCount(); self.table.insertRow(r); self.table.setItem(r,0,QTableWidgetItem(ext)); c=QComboBox(); c.addItems(ACTIONS); c.setCurrentText(action); self.table.setCellWidget(r,1,c); self.table.setItem(r,2,QTableWidgetItem(folder))
    def remove_row(self):
        r=self.table.currentRow()
        if r>=0: self.table.removeRow(r)
    def save(self):
        out={}
        for r in range(self.table.rowCount()):
            ext=norm_ext(self.table.item(r,0).text() if self.table.item(r,0) else '')
            if not ext: continue
            action=self.table.cellWidget(r,1).currentText(); folder=self.table.item(r,2).text().strip() if self.table.item(r,2) else ''
            out[ext]={'action':action};
            if folder: out[ext]['folder']=folder
        self.changed.emit(out); self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP_NAME); self.setMinimumSize(960,700); self.resize(1080,780); self.setWindowIcon(make_icon()); self.settings=QSettings('ChomonTools',APP_NAME); self.rules=self.load_rules(); self.history=self.load_history(); self.rows=[]; self.last_ops=[]; self.root=''; self.dark=self.settings.value('dark',False,type=bool); self.build_ui(); self.apply_theme(); self.update_ui(); QTimer.singleShot(1800, lambda: self.check_for_updates(True))
    def load_rules(self):
        raw=self.settings.value('rules_json','')
        if raw:
            try:return json.loads(raw)
            except:pass
        return default_rules()
    def save_rules(self): self.settings.setValue('rules_json',json.dumps(self.rules))
    def load_history(self):
        try:return json.loads(self.settings.value('history_json','[]'))
        except:return []
    def save_history(self): self.settings.setValue('history_json',json.dumps(self.history[-100:]))
    def build_ui(self):
        c=QWidget(); c.setObjectName('Background'); self.setCentralWidget(c); outer=QVBoxLayout(c); outer.setContentsMargins(38,30,38,30); outer.setSpacing(18)
        top=QHBoxLayout(); tb=QVBoxLayout(); t=QLabel('Embroidery Sorter'); t.setObjectName('Title'); s=QLabel('Fast, safe and fully configurable file organization.'); s.setObjectName('Subtitle'); tb.addWidget(t); tb.addWidget(s); top.addLayout(tb); top.addStretch(); self.update_btn=QPushButton('Check for Updates'); self.update_btn.setObjectName('SecondaryButton'); self.update_btn.setMinimumHeight(42); self.update_btn.clicked.connect(self.check_for_updates); top.addWidget(self.update_btn); self.theme_btn=QPushButton('☾ Dark'); self.theme_btn.setObjectName('SecondaryButton'); self.theme_btn.clicked.connect(self.toggle_theme); top.addWidget(self.theme_btn); outer.addLayout(top)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs,1)
        home=QWidget(); hl=QVBoxLayout(home); hl.setContentsMargins(5,15,5,5); hl.setSpacing(14)
        card=QFrame(); card.setObjectName('Card'); cl=QVBoxLayout(card); cl.setContentsMargins(24,22,24,22); lab=QLabel('SOURCE FOLDER'); lab.setObjectName('SectionLabel'); cl.addWidget(lab); row=QHBoxLayout(); self.path=DropLineEdit(); self.path.setPlaceholderText('Drag & drop a folder here, or choose one…'); self.path.folderDropped.connect(self.set_folder); row.addWidget(self.path,1); b=QPushButton('Choose Folder'); b.setObjectName('SecondaryButton'); b.clicked.connect(self.choose); row.addWidget(b); cl.addLayout(row); hint=QLabel('Only files directly inside this folder are processed. Existing subfolders are never scanned.'); hint.setObjectName('Info'); hint.setWordWrap(True); cl.addWidget(hint); hl.addWidget(card)
        stats=QHBoxLayout(); self.stat={}
        for key,name in [('move','MOVE'),('keep','KEEP'),('delete','SAFE TRASH'),('recycle','RECYCLE BIN')]:
            box=QFrame(); box.setObjectName('StatBox'); bl=QVBoxLayout(box); n=QLabel('0'); n.setObjectName('StatNumber'); q=QLabel(name); q.setObjectName('StatName'); bl.addWidget(n); bl.addWidget(q); stats.addWidget(box); self.stat[key]=n
        hl.addLayout(stats); preview=QFrame(); preview.setObjectName('Card'); pl=QVBoxLayout(preview); head=QHBoxLayout(); h=QLabel('Preview'); h.setObjectName('PreviewTitle'); self.status=QLabel('Choose a folder.'); self.status.setObjectName('Status'); head.addWidget(h); head.addStretch(); head.addWidget(self.status); pl.addLayout(head); self.list=QListWidget(); pl.addWidget(self.list,1); hl.addWidget(preview,1)
        self.progress=QProgressBar(); self.progress.setVisible(False); self.progress.setTextVisible(False); self.progress.setFixedHeight(6); hl.addWidget(self.progress); bottom=QHBoxLayout(); self.undo=QPushButton('↶ Undo Last Operation'); self.undo.setObjectName('SecondaryButton'); self.undo.clicked.connect(self.undo_last); self.organize=QPushButton('Organize Files'); self.organize.setObjectName('PrimaryButton'); self.organize.setMinimumHeight(50); self.organize.clicked.connect(self.organize_files); bottom.addWidget(self.undo); bottom.addStretch(); bottom.addWidget(self.organize); hl.addLayout(bottom); self.tabs.addTab(home,'Organizer')
        rt=QWidget(); rl=QVBoxLayout(rt); rc=QFrame(); rc.setObjectName('Card'); rcl=QVBoxLayout(rc); x=QLabel('Rules & Automation'); x.setObjectName('PreviewTitle'); rcl.addWidget(x); z=QLabel('Choose exactly which extensions are kept, moved, safely trashed, ignored, or sent to the Windows Recycle Bin.'); z.setObjectName('Info'); z.setWordWrap(True); rcl.addWidget(z); edit=QPushButton('Open Rules Editor'); edit.setObjectName('PrimaryButton'); edit.setMinimumHeight(48); edit.clicked.connect(self.open_rules); rcl.addWidget(edit); rl.addWidget(rc); rl.addStretch(); self.tabs.addTab(rt,'Rules')
        ht=QWidget(); hil=QVBoxLayout(ht); hc=QFrame(); hc.setObjectName('Card'); hcl=QVBoxLayout(hc); hh=QHBoxLayout(); x=QLabel('Activity History'); x.setObjectName('PreviewTitle'); clear=QPushButton('Clear History'); clear.clicked.connect(self.clear_history); hh.addWidget(x); hh.addStretch(); hh.addWidget(clear); hcl.addLayout(hh); self.history_list=QListWidget(); hcl.addWidget(self.history_list); hil.addWidget(hc); self.tabs.addTab(ht,'History')
        self.refresh_history()
    def set_folder(self,f): self.root=f; self.path.setText(f); self.scan()
    def choose(self):
        f=QFileDialog.getExistingDirectory(self,'Choose source folder')
        if f:self.set_folder(f)
    def open_rules(self):
        d=RulesDialog(self,self.rules); d.changed.connect(self.set_rules); d.exec()
    def set_rules(self,r): self.rules=r; self.save_rules(); self.scan() if self.root else None
    def scan(self):
        self.setEnabled(False); self.status.setText('Scanning…'); self.list.clear(); self.scan_worker=ScanWorker(self.root,self.rules); self.scan_worker.done.connect(self.scan_done); self.scan_worker.failed.connect(self.worker_failed); self.scan_worker.start()
    def scan_done(self,rows):
        self.setEnabled(True); self.rows=rows; c={'move':0,'keep':0,'delete':0,'recycle':0}
        for _,a,_ in rows:
            if a=='Move to matching folder':c['move']+=1
            elif a=='Keep':c['keep']+=1
            elif a=='Safe Trash (undoable)':c['delete']+=1
            elif a=='Recycle Bin':c['recycle']+=1
        for k,v in c.items():self.stat[k].setText(str(v))
        self.list.clear()
        for p,a,t in rows:self.list.addItem(QListWidgetItem(f'{a.upper():<28} {p.name}'+(f'  →  {t.name}/' if t else '')))
        self.status.setText(f'{len(rows)} file(s) ready'); self.update_ui()
    def organize_files(self):
        if not self.rows:return
        if QMessageBox.question(self,'Confirm','Process the files shown in Preview?\n\nSafe Trash items are undoable. Recycle Bin items use the Windows Recycle Bin.',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)!=QMessageBox.Yes:return
        self.setEnabled(False); self.progress.setVisible(True); self.progress.setValue(0); self.worker=SortWorker(self.rows,self.root); self.worker.progress.connect(lambda v,s:(self.progress.setValue(v),self.status.setText(s))); self.worker.done.connect(self.sort_done); self.worker.failed.connect(self.worker_failed); self.worker.start()
    def sort_done(self,r):
        self.setEnabled(True); self.progress.setVisible(False); self.last_ops=r['ops']; c=r['counts']
        if self.last_ops:self.history.append({'time':now(),'folder':self.root,'counts':c,'ops':self.last_ops}); self.save_history()
        msg=f"Moved: {c['moved']}\nSafe Trash: {c['trashed']}\nRecycle Bin: {c['recycled']}\nKept: {c['kept']}\nSkipped: {c['skipped']}"; self.notify('Organization complete',msg.replace('\n','  •  ')); QMessageBox.information(self,'Done',msg); self.refresh_history(); self.scan()
    def undo_last(self):
        if not self.last_ops: QMessageBox.information(self,'Undo','There is no undoable operation yet.'); return
        n=0
        for op in reversed(self.last_ops):
            try:
                src,dest=Path(op['src']),Path(op['dest'])
                if dest.exists() and not src.exists():src.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(dest),str(src)); n+=1
            except:pass
        self.last_ops=[]; self.notify('Undo complete',f'Restored {n} file(s).'); self.update_ui(); self.scan()
    def refresh_history(self):
        if not hasattr(self,'history_list'):return
        self.history_list.clear()
        for h in reversed(self.history):
            c=h.get('counts',{}); self.history_list.addItem(f"{h.get('time','')}  •  {Path(h.get('folder','')).name}  •  Moved {c.get('moved',0)}  •  Safe Trash {c.get('trashed',0)}  •  Recycle {c.get('recycled',0)}")
    def clear_history(self): self.history=[]; self.save_history(); self.refresh_history()
    def notify(self,title,text):
        if QSystemTrayIcon.isSystemTrayAvailable():
            if not hasattr(self,'tray'):self.tray=QSystemTrayIcon(make_icon(),self); self.tray.show()
            self.tray.showMessage(title,text,QSystemTrayIcon.Information,4000)
    def check_for_updates(self, silent=False):
        self.update_btn.setEnabled(False)
        self.update_worker=UpdateWorker()
        self.update_worker.finished.connect(lambda result:self.update_check_done(result,silent))
        self.update_worker.start()
    def update_check_done(self,result,silent=False):
        self.update_btn.setEnabled(True)
        if not result.get('ok'):
            if not silent: QMessageBox.warning(self,'Updates',f"Could not check for updates.\n\n{result.get('message','Unknown error')}")
            return
        if not result.get('update'):
            if not silent: QMessageBox.information(self,'Updates',f'You are up to date.\n\nVersion {APP_VERSION}')
            return
        v=result['version']; notes=result.get('notes','') or 'A newer version is available.'
        if QMessageBox.question(self,'Update available',f'Embroidery Sorter Pro {v} is available.\n\n{notes}\n\nDownload and install it now?',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)!=QMessageBox.Yes:
            return
        try:
            tmp=Path(tempfile.gettempdir())/f'Embroidery_Sorter_Pro_Setup_{v}.exe'
            urllib.request.urlretrieve(result['url'],str(tmp))
            subprocess.Popen([str(tmp)],shell=False)
            QApplication.instance().quit()
        except Exception as e:
            QMessageBox.critical(self,'Update failed',f'Could not download the update.\n\n{e}')

    def toggle_theme(self): self.dark=not self.dark; self.settings.setValue('dark',self.dark); self.theme_btn.setText('☀ Light' if self.dark else '☾ Dark'); self.apply_theme()
    def apply_theme(self):
        if self.dark:
            bg,card,fg,muted,soft,border='#151517','#202023','#F5F5F7','#A5A5AA','#2A2A2E','#36363B'; primary_bg='#F5F5F7'; primary_fg='#111111'
        else:
            bg,card,fg,muted,soft,border='#F5F5F7','#FFFFFF','#171719','#77777C','#F7F7F8','#E7E7E9'; primary_bg='#111111'; primary_fg='#FFFFFF'
        self.setStyleSheet(f'''QWidget#Background {{ background:{bg}; color:{fg}; font-family:"Segoe UI"; }} QFrame#Card {{ background:{card}; border:1px solid {border}; border-radius:18px; }} QLabel#Title {{ font-size:30px; font-weight:700; color:{fg}; }} QLabel#Subtitle,QLabel#Status {{ font-size:13px; color:{muted}; }} QLabel#SectionLabel,QLabel#StatName {{ font-size:10px; font-weight:700; color:{muted}; }} QLineEdit {{ background:{soft}; border:1px solid {border}; border-radius:12px; padding:0 14px; min-height:46px; color:{fg}; }} QPushButton#SecondaryButton {{ background:{soft}; border:1px solid {border}; border-radius:12px; padding:0 16px; color:{fg}; font-weight:600; min-height:42px; }} QPushButton#PrimaryButton {{ background:{primary_bg}; color:{primary_fg}; border:none; border-radius:13px; padding:0 22px; font-weight:700; }} QFrame#StatBox {{ background:{soft}; border:1px solid {border}; border-radius:13px; }} QLabel#StatNumber {{ font-size:25px; font-weight:700; color:{fg}; }} QLabel#PreviewTitle {{ font-size:15px; font-weight:700; color:{fg}; }} QLabel#Info {{ background:{soft}; border-radius:10px; padding:12px; color:{muted}; }} QListWidget,QTableWidget {{ background:{soft}; border:1px solid {border}; border-radius:12px; color:{fg}; padding:6px; }} QTabBar::tab {{ padding:10px 16px; color:{muted}; }} QTabBar::tab:selected {{ color:{fg}; font-weight:700; }} QComboBox {{ min-height:36px; background:{soft}; color:{fg}; border:1px solid {border}; border-radius:8px; padding:0 8px; }} QProgressBar {{ background:{soft}; border:none; border-radius:3px; height:6px; }} QProgressBar::chunk {{ background:{fg}; border-radius:3px; }}''')
    def worker_failed(self,msg): self.setEnabled(True); self.progress.setVisible(False); QMessageBox.critical(self,'Error',msg)
    def update_ui(self): self.organize.setEnabled(bool(self.rows)); self.undo.setEnabled(bool(self.last_ops))

def main():
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setStyle('Fusion'); w=MainWindow(); w.show(); sys.exit(app.exec())
if __name__=='__main__':main()
