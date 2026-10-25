const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
let backendProcess = null;
let backendStartedByApp = false;
function ensureLogDir(){const dir=path.join(app.getPath('userData'),'logs');fs.mkdirSync(dir,{recursive:true});return dir}
function possibleBackendCommands(){const rootDir=path.resolve(__dirname,'..');const packagedRoot=process.resourcesPath||rootDir;const isWin=process.platform==='win32';return [isWin?{cmd:'python',args:[path.join(rootDir,'backend','main.py')],cwd:path.join(rootDir,'backend')}:{cmd:'python3',args:[path.join(rootDir,'backend','main.py')],cwd:path.join(rootDir,'backend')},isWin?{cmd:'py',args:[path.join(rootDir,'backend','main.py')],cwd:path.join(rootDir,'backend')}:null,isWin?{cmd:path.join(packagedRoot,'backend_dist','hel_backend.exe'),args:[],cwd:packagedRoot}:null].filter(Boolean)}
function startBackend(){const commands=possibleBackendCommands();const logDir=ensureLogDir();const out=fs.openSync(path.join(logDir,'backend.out.log'),'a');const err=fs.openSync(path.join(logDir,'backend.err.log'),'a');for(const item of commands){try{if(item.cmd.endsWith('.exe')&&!fs.existsSync(item.cmd))continue;backendProcess=spawn(item.cmd,item.args,{cwd:item.cwd,env:{...process.env},stdio:['ignore',out,err],detached:false,windowsHide:true});backendStartedByApp=true;backendProcess.on('error',()=>{});backendProcess.on('exit',()=>{backendProcess=null;backendStartedByApp=false});return}catch(_){}}}
function backendLogsHint(){return path.join(app.getPath('userData'),'logs')}
function stopBackend(){if(backendProcess&&backendStartedByApp&&!backendProcess.killed){backendProcess.kill()}}
function createWindow(){startBackend();const win=new BrowserWindow({width:1400,height:900,minWidth:1100,minHeight:700,show:false,webPreferences:{preload:path.join(__dirname,'preload.js'),nodeIntegration:false,contextIsolation:true},title:'Проект Хель'});win.once('ready-to-show',()=>win.show());win.webContents.on('did-fail-load',()=>{console.error('[Hel] UI load failed. Logs:', backendLogsHint())});win.loadFile(path.join(__dirname,'index.html'))}
app.whenReady().then(createWindow);app.on('window-all-closed',()=>{stopBackend();if(process.platform!=='darwin')app.quit()});app.on('before-quit',stopBackend);
