import React,{useCallback,useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api,send,saveSession,signedIn} from './api';
import './style.css';

const fmt=(n,unit='')=>typeof n==='number' && Number.isFinite(n)?`${n.toFixed(2)}${unit}`:'Unavailable';
const time=s=>s?new Date(s).toLocaleString():'Not received';
const fields=form=>Object.fromEntries(new FormData(form));
function Field({label,...props}) {return <label>{label}<input {...props}/></label>;}
function ErrorBox({error}) {return error?<p className="error" role="alert">{error}</p>:null;}
function Login({onLogin}) {
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  return <main className="login"><img src="/logo.svg" alt="SmartDB"/><div className="eyebrow">DEVELOPER CONSOLE</div><h1>Welcome back.</h1>
    <p>Sign in to test SmartDB devices and the backend API.</p><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try {
      const result=await send('/auth/login',fields(e.currentTarget));saveSession(result);onLogin();
    }catch(error){setError(error.message);}finally{setBusy(false);}}}>
      <Field label="Email" name="email" type="email" autoComplete="username" required/>
      <Field label="Password" name="password" type="password" minLength={8} autoComplete="current-password" required/>
      <ErrorBox error={error}/><button disabled={busy}>{busy?'Signing in…':'Sign in'}</button>
    </form><a href="https://smartdb-docs.vercel.app">Setup and documentation ↗</a></main>;
}
function Trend({samples}) {
  const values=[...samples].reverse().map(x=>x.current);
  if (!values.some(v=>typeof v==='number')) return <p className="empty">Current history appears after the board sends telemetry.</p>;
  const max=Math.max(1,...values.filter(v=>typeof v==='number'));
  let paths=[],segment=[];
  values.forEach((v,i)=>{if(typeof v==='number') segment.push(`${20+i*760/Math.max(1,values.length-1)},${150-v/max*120}`);
    else {if(segment.length) paths.push(segment);segment=[];}});if(segment.length)paths.push(segment);
  return <><svg className="chart" viewBox="0 0 800 180" role="img" aria-label="AC RMS current history, oldest to newest">
    {[30,90,150].map(y=><line key={y} x1="20" x2="780" y1={y} y2={y} stroke="#dbe6e5"/>)}
    {paths.map((p,i)=><polyline key={i} points={p.join(' ')} fill="none" stroke="#14796d" strokeWidth="3"/>)}
    <text x="20" y="175">Oldest</text><text x="720" y="175">Newest</text>
  </svg><small>Scale: 0–{max.toFixed(1)} A · Gaps indicate unavailable samples.</small></>;
}
function FusionPreview({deviceId}) {
  const [frame,setFrame]=useState(null),[error,setError]=useState(''),[clock,setClock]=useState(Date.now());
  useEffect(()=>{
    let active=true,url;
    const load=async()=>{try{
      const result=await api(`/devices/${encodeURIComponent(deviceId)}/fusion/frame`,{binary:true});
      if(!active)return;
      if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(result.blob);
      setFrame({url,received:result.headers.get('X-Received-At'),sequence:result.headers.get('X-Fusion-Sequence'),synthetic:result.headers.get('X-Synthetic')==='true'});setError('');
    }catch(e){if(active)setError(e.status===404?'No fused preview uploaded yet.':e.message);}};
    load();const poll=setInterval(load,30000),tick=setInterval(()=>setClock(Date.now()),1000);
    return()=>{active=false;clearInterval(poll);clearInterval(tick);if(url)URL.revokeObjectURL(url);};
  },[deviceId]);
  const age=frame?Math.max(0,Math.floor((clock-Date.parse(frame.received))/1000)):null;
  return <section className="card"><div className="section-head"><h2>RGB + thermal preview</h2><span>Stored snapshot · not live video</span></div>
    {error?<p className="muted">{error}</p>:null}
    {frame?<><img className="fusion-preview" src={frame.url} alt="Stored RGB image with registered thermal overlay"/>
      <p className={frame.synthetic?'warning':'muted'}>{frame.synthetic?'Synthetic preview · ':''}Received {age} seconds ago · sequence {frame.sequence}{age>120?' · stale':''}</p></>:null}
    <p className="muted">Uploads at most once every 30 seconds when fusion is calibrated and fresh. Thermal measurements use the native 32 × 24 samples.</p></section>;
}
function App() {
  const [logged,setLogged]=useState(signedIn),[tab,setTab]=useState('Overview'),[profile,setProfile]=useState(null);
  const [devices,setDevices]=useState([]),[selected,setSelected]=useState(''),[sample,setSample]=useState(null),[status,setStatus]=useState(null);
  const [history,setHistory]=useState([]),[alerts,setAlerts]=useState([]),[notifications,setNotifications]=useState([]),[commands,setCommands]=useState([]);
  const [config,setConfig]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[credential,setCredential]=useState(null);
  const [lastRefresh,setLastRefresh]=useState(null),[connected,setConnected]=useState(false);
  const generation=useRef(0);
  const reload=useCallback(async()=>{
    if(!logged)return;const g=++generation.current;
    try{
      const [me,list,alarms,notes]=await Promise.all([api('/users/me'),api('/devices'),api('/alerts'),api('/notifications')]);
      if(g!==generation.current)return;
      setProfile(me);setDevices(list);setAlerts(alarms);setNotifications(notes);
      const id=list.some(x=>x.device_id===selected)?selected:list[0]?.device_id || '';
      if(id!==selected){setSelected(id);return;}
      if(id){
        const root=`/devices/${encodeURIComponent(id)}`;
        const [latest,health,rows,desired,queue]=await Promise.all([
          api(root+'/telemetry/latest').catch(e=>{if(e.status===404)return null;throw e;}),api(root+'/status'),
          api(root+'/telemetry?limit=100'),api(root+'/config'),api(root+'/commands')]);
        if(g!==generation.current)return;
        setSample(latest);setStatus(health);setHistory(rows);setConfig(desired);setCommands(queue.commands);
      }
      setConnected(true);setLastRefresh(new Date());setError('');
    }catch(e){if(g===generation.current){setError(e.message);setConnected(false);}}
  },[logged,selected]);
  useEffect(()=>{reload();const id=setInterval(reload,5000);return()=>{clearInterval(id);generation.current++;};},[reload]);
  const reset=()=>{generation.current++;setLogged(false);setCredential(null);setProfile(null);setDevices([]);setSelected('');setSample(null);setStatus(null);setHistory([]);setAlerts([]);setNotifications([]);setCommands([]);setConfig(null);setConnected(false);setLastRefresh(null);setNotice('');setError('');};
  useEffect(()=>{window.addEventListener('smartdb-logout',reset);return()=>window.removeEventListener('smartdb-logout',reset);},[]);
  const action=async(fn,message)=>{setBusy(true);setError('');setNotice('');try{await fn();setNotice(message);await reload();}catch(e){setError(e.message);}finally{setBusy(false);}};
  if(!logged)return <Login onLogin={()=>setLogged(true)}/>;
  const device=devices.find(d=>d.device_id===selected),base=`/devices/${encodeURIComponent(selected)}`;
  const stale=!connected || !status?.online,write=profile && profile.role!=='viewer';
  return <div className="shell"><aside><a className="brand" href="#" aria-label="SmartDB overview" onClick={()=>setTab('Overview')}><img src="/logo.svg" alt="SmartDB"/></a>
    <div className="eyebrow">CONTROL ROOM</div><nav>{['Overview','History','Alerts','Devices','Settings'].map(name=><button key={name} className={tab===name?'active':''} onClick={()=>setTab(name)}>{name}{name==='Alerts' && alerts.some(a=>a.status==='active')?<span className="count">{alerts.filter(a=>a.status==='active').length}</span>:null}</button>)}</nav>
    <a className="docs" href="https://smartdb-docs.vercel.app" target="_blank" rel="noreferrer">Documentation ↗</a>
    <div className="account"><strong>{profile?.name || 'Loading…'}</strong><small>{profile?.role}</small><button onClick={()=>action(async()=>{
      const s=JSON.parse(sessionStorage.getItem('smartdb-session'));try{if(s)await send('/auth/logout',{refresh_token:s.refresh_token});}finally{saveSession(null);reset();}
    },'Signed out')}>Sign out</button></div></aside>
    <main><header><div><div className="eyebrow">SMARTDB / {tab.toUpperCase()}</div><h1>{tab==='Overview'?'Your installation, at a glance.':tab}</h1></div><div className="connection"><span className={'dot '+(connected?'ok':'')}/>{connected?'Connected to server':'Server unavailable'}<small>{lastRefresh?`Updated ${lastRefresh.toLocaleTimeString()}`:'Waiting for data'}</small></div></header>
      <div className="toolbar"><label>Installation<select value={selected} onChange={e=>{setSelected(e.target.value);setSample(null);setStatus(null);setHistory([]);setCredential(null);setConfig(null);}}><option value="">Select device</option>{devices.map(d=><option value={d.device_id} key={d.device_id}>{d.device_name} · {d.location}</option>)}</select></label><button className="secondary" onClick={reload}>Refresh</button><span className="scope">Isolated AC bench · max 1 A</span></div>
      <ErrorBox error={error}/>{notice?<p role="status" className="notice">{notice}</p>:null}
      {sample?.synthetic?<p className="warning">Synthetic demo data — these are not installation measurements.</p>:null}
      {!devices.length && tab!=='Devices'?<section className="card empty"><h2>Add your first SmartDB</h2><p>Create a device, provision its upload credential and apply it with the firmware setup menu.</p><button onClick={()=>setTab('Devices')}>Set up a device</button></section>:null}
      {tab==='Overview' && device?<>
        <section className="metrics">{[['AC RMS current',fmt(sample?.current,' A')],['Thermal maximum',fmt(sample?.temperature,' °C')],['Relay',sample?.relay_state || 'Unknown'],['Protection',sample?.protection_state || 'Unknown']].map(([label,value])=><article className="card metric" key={label}><span>{label}</span><strong>{value}</strong><small>{stale?'Last received · device offline':sample?'Latest reported':'Waiting for telemetry'}</small></article>)}</section>
        <div className="grid"><section className="card"><div className="section-head"><h2>Current over time</h2><span>Last {history.length} samples</span></div><Trend samples={history}/></section>
        <section className="card"><h2>Board status</h2><dl><dt>Last received</dt><dd>{time(status?.last_seen)}</dd><dt>Firmware</dt><dd>{status?.firmware || 'Unknown'}</dd><dt>Protection reason</dt><dd>{sample?.protection_reason || 'Unknown'}</dd><dt>Commissioned</dt><dd>{sample?String(sample.commissioned ?? 'Unknown'):'Unknown'}</dd><dt>Storage</dt><dd>{sample?.storage_ok===undefined?'Unknown':sample.storage_ok?'Healthy':'Fault'}</dd></dl>
          <button className="danger" disabled={busy || !write} onClick={()=>{if(window.confirm('Queue OPEN RELAY? Delivery requires the board to be online. Physical re-arm will be required.'))action(()=>send(base+'/commands',{command:'OPEN_RELAY'}),'Open request queued. Check the acknowledgement below.');}}>Open relay</button><p className="muted">Cloud commands require connectivity. Physical BOOT re-arm is always required to close the relay.</p></section></div>
        <section className="card"><div className="section-head"><h2>Thermal regions</h2><span>{sample?.vision?.ready&&!stale?'Registered frame available':'Frame unavailable or stale'}</span></div><p>{sample?.vision?.reason || 'Waiting for camera and thermal data.'}</p><div className="table-wrap"><table><thead><tr><th>Region</th><th>Native samples</th><th>Maximum</th><th>Mean</th><th>Quality</th></tr></thead><tbody>{sample?.vision?.regions?.map(r=><tr key={r.id}><td>{r.id}</td><td>{r.samples}</td><td>{r.supported&&!stale?fmt(r.max_c,' °C'):'Unavailable'}</td><td>{r.supported&&!stale?fmt(r.mean_c,' °C'):'Unavailable'}</td><td>{r.supported&&!stale?'Supported':r.ambiguous?'Ambiguous':'Unavailable'}</td></tr>)}</tbody></table></div></section>
        <FusionPreview key={selected} deviceId={selected}/><CommandList commands={commands}/>
      </>:null}
      {tab==='History' && device?<><section className="card"><h2>Telemetry history</h2><p>Newest received first. Voltage and power remain unavailable when the board does not measure them.</p><Trend samples={history}/><div className="table-wrap"><table><thead><tr><th>Device time</th><th>Current</th><th>Temperature</th><th>Relay</th><th>Quality</th></tr></thead><tbody>{history.map((s,i)=><tr key={s.sample_id || i}><td>{s.timestamp?time(s.timestamp):'Clock not synchronized'}</td><td>{fmt(s.current,' A')}</td><td>{fmt(s.temperature,' °C')}</td><td>{s.relay_state || 'Unknown'}</td><td>{s.synthetic?'Synthetic':s.time_quality || 'Unknown'}</td></tr>)}</tbody></table></div></section><section className="card"><h2>Recent board events</h2>{sample?.events?.length?<div className="table-wrap"><table><thead><tr><th>Boot</th><th>Uptime</th><th>State</th><th>Reason</th></tr></thead><tbody>{sample.events.map(e=><tr key={`${e.boot_id}:${e.sequence}`}><td>{e.boot_id}</td><td>{(e.uptime_ms/1000).toFixed(1)} s</td><td>{e.state}</td><td>{e.reason}</td></tr>)}</tbody></table></div>:<p>No events received.</p>}</section></>:null}
      {tab==='Alerts'?<><section className="card"><h2>Protection and operator alerts</h2>{alerts.length?alerts.map(a=><article className="alert" key={a.id}><div><span className={'badge '+a.severity}>{a.severity} · {a.status}</span><h3>{a.message}</h3><small>{a.device_id} · {time(a.created_at)}</small></div>{a.status==='active'&&write?<button className="secondary" disabled={busy} onClick={()=>action(()=>send(`/alerts/${a.id}/resolve`,{message:'Reviewed in dashboard'},'PUT'),'Alert resolved. This does not re-arm the relay.')}>Mark resolved</button>:null}</article>):<p>No alerts recorded.</p>}</section><section className="card"><h2>Notifications</h2>{notifications.map(n=><article className="alert" key={n.id}><span>{n.title}</span><button className="secondary" onClick={()=>action(()=>send(`/notifications/${n.id}/read`,{read:!n.read},'PATCH'),'Notification updated')}>{n.read?'Mark unread':'Mark read'}</button></article>)}</section></>:null}
      {tab==='Devices'?<><section className="card"><h2>Register an installation</h2><form className="form-grid" onSubmit={e=>{e.preventDefault();const data=fields(e.currentTarget),form=e.currentTarget;action(async()=>{const d=await send('/devices',{...data,device_type:'ESP32'});setSelected(d.device_id);form.reset();},'Device created. Provision its credential below.');}}><Field label="Device name" name="device_name" required maxLength={200}/><Field label="Location" name="location" required maxLength={200}/><button disabled={busy||!write}>Create device</button></form></section>
        <section className="card"><h2>Provision selected board</h2><p>Administrator access required. The device credential is shown once and authorizes this board only.</p><form className="form-grid" onSubmit={e=>{e.preventDefault();const data=fields(e.currentTarget);action(async()=>setCredential(await send('/device/register',{...data,device_id:selected})),'Credential created. Save it to the S3 with the setup menu.');}}><Field label="Serial number" name="serial_number" required/><Field label="Hardware" name="hardware" defaultValue="SmartDB v2 S3" required/><Field label="Firmware version" name="firmware" defaultValue="v2-bench" required/><button disabled={busy||!selected||profile?.role!=='admin'}>Issue device credential</button></form>
          <button className="secondary" disabled={busy||!selected||profile?.role!=='admin'} onClick={()=>{if(window.confirm('Replace this board’s credential? Its previous credential stops working immediately. Save the replacement to the S3 setup menu.'))action(async()=>setCredential(await send(base+'/credential/rotate',{})),'Credential replaced. Update the board before it can upload again.');}}>Replace lost credential</button>
          {credential?<div className="credential"><h3>Save this credential now</h3><label>Telemetry URL<input readOnly value={`${location.origin}/api/v1/devices/${credential.device_id}/telemetry`}/></label><label>Telemetry token<textarea readOnly value={credential.device_key}/></label><p>Use these in the S3 setup menu. A physical board requires a reachable HTTPS endpoint; localhost emulators are for software development.</p><button className="secondary" onClick={()=>setCredential(null)}>I saved it — hide credential</button></div>:null}</section>
        <section className="card"><h2>Registered devices</h2>{devices.map(d=><article className="alert" key={d.device_id}><div><h3>{d.device_name}</h3><small>{d.location} · {d.device_id}</small></div><span className="badge">{d.status}</span></article>)}</section></>:null}
      {tab==='Settings'?<><section className="card"><h2>Profile</h2><form className="form-grid" onSubmit={e=>{e.preventDefault();action(()=>send('/users/me',fields(e.currentTarget),'PATCH'),'Profile updated');}}><Field key={profile?.name} label="Name" name="name" defaultValue={profile?.name} required maxLength={100}/><button disabled={busy}>Save name</button></form></section>
        {device&&config?<section className="card"><h2>Board configuration</h2><p>Saving queues a configuration change. Applying it opens the relay and requires physical re-arm. Calibration and commissioning remain in the local setup menu.</p><form className="form-grid" key={selected} onSubmit={e=>{e.preventDefault();const raw=fields(e.currentTarget);action(()=>send(base+'/config',Object.fromEntries(Object.entries(raw).map(([k,v])=>[k,Number(v)])),'PUT'),'Configuration queued; check the device acknowledgement.');}}><Field label="Current limit (A)" name="max_current" type="number" min="0.01" max="1" step="0.01" defaultValue={config.max_current} required/><Field label="Temperature limit (°C)" name="max_temperature" type="number" min="20" max="100" step="0.1" defaultValue={config.max_temperature} required/><Field label="Telemetry interval (seconds)" name="sampling_rate" type="number" min="5" max="60" step="1" defaultValue={config.sampling_rate} required/><button disabled={busy||!write}>Save and request application</button></form><button className="secondary" disabled={busy||!write} onClick={()=>action(()=>send(base+'/commands',{command:'REQUEST_STATUS'}),'Status request queued')}>Request fresh status</button></section>:null}
        <CommandList commands={commands}/><section className="card"><h2>Notifications</h2><p>In-app alerts are available. Email, SMS and push delivery are not configured.</p></section></>:null}
      <footer>SmartDB v2 · Local protection remains independent of the cloud.</footer>
    </main></div>;
}
function CommandList({commands}) {return <section className="card"><h2>Command acknowledgements</h2>{commands.length?<div className="table-wrap"><table><thead><tr><th>Command</th><th>Requested</th><th>Result</th><th>Detail</th></tr></thead><tbody>{commands.slice(0,10).map(c=><tr key={c.command_id}><td>{c.command}</td><td>{time(c.created_at)}</td><td><span className="badge">{c.status}</span></td><td>{c.detail || (c.status==='queued'?'Awaiting board':'—')}</td></tr>)}</tbody></table></div>:<p>No commands issued.</p>}</section>;}
createRoot(document.getElementById('root')).render(<App/>);
