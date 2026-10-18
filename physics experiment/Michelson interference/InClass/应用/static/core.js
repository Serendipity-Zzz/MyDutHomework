/* Pure numerical functions shared by the interface and validation scripts. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabCore=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const calibration=Object.freeze({umPerTurn:10,divisions:100,umPerDivision:0.1});
  function number(value,label){if(value===''||value===null||value===undefined||!Number.isFinite(Number(value)))throw new Error(label+'需要填写有效数字');return Number(value);}
  function displacement(value,unit){const x=number(value,'位移或圈数');if(x<=0)throw new Error('位移或圈数必须大于 0');if(!['turn','division','um','mm'].includes(unit))throw new Error('未知单位');return x*({turn:10,division:.1,um:1,mm:1000}[unit]);}
  function interpolate(peaks,time){if(!Array.isArray(peaks)||peaks.length<2)return null;const t=number(time,'时间');if(t<peaks[0]-1e-7||t>peaks.at(-1)+1e-7)return null;let lo=0,hi=peaks.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(peaks[mid]<=t)lo=mid;else hi=mid;}return lo+(t-peaks[lo])/(peaks[hi]-peaks[lo]);}
  function countBetween(peaks,start,end){const a=number(start,'起始时间'),b=number(end,'结束时间');if(b<=a)throw new Error('结束时间须晚于起始时间');const x=interpolate(peaks,a),y=interpolate(peaks,b);return x===null||y===null?null:y-x;}
  function linearFit(points,throughOrigin=false){if(points.length<2)return null;const n=points.length,mx=throughOrigin?0:points.reduce((s,p)=>s+p[0],0)/n,my=throughOrigin?0:points.reduce((s,p)=>s+p[1],0)/n;let xx=0,xy=0;for(const [x,y]of points){xx+=(x-mx)**2;xy+=(x-mx)*(y-my);}if(xx<1e-16)return null;const slope=xy/xx,intercept=throughOrigin?0:my-slope*mx;const sse=points.reduce((s,[x,y])=>s+(y-slope*x-intercept)**2,0),ybar=points.reduce((s,p)=>s+p[1],0)/n,sst=points.reduce((s,p)=>s+(p[1]-ybar)**2,0),dof=n-(throughOrigin?1:2);return{slope,intercept,r2:sst<1e-14?(sse<1e-14?1:0):1-sse/sst,slopeSE:dof>0?Math.sqrt(sse/dof/xx):null,sse,n};}
  function wavelength(rows,reference=632.8){
    reference=number(reference,'参考波长');if(reference<=0)throw new Error('参考波长须大于 0');
    const records=rows.filter(r=>r.enabled!==false).map((r,i)=>{const N=number(r.N,'第 '+(i+1)+' 段条纹数');if(N<=0)throw new Error('条纹数必须大于 0');const d=displacement(r.amount,r.unit),start=number(r.start,'起始时间'),end=number(r.end,'结束时间');if(start<0||end<=start)throw new Error('第 '+(i+1)+' 段时间无效');return{...r,N,d,start,end,lambda:2000*d/N};});
    if(!records.length)return null;
    const points=[[0,0]];let cumN=0,cumD=0;for(const r of records){cumN+=r.N;cumD+=r.d;points.push([cumN,cumD]);}
    const contiguous=records.every((r,i)=>i===0||Math.abs(r.start-records[i-1].end)<.02);
    // Independent intervals use delta-d = a*N through origin; no invented motion in gaps.
    const fit=contiguous?linearFit(points):linearFit(records.map(r=>[r.N,r.d]),true);
    const lambdaFit=fit?2000*fit.slope:null;
    const total=2000*cumD/cumN;
    const equalD=contiguous&&records.length>=3&&records.every(r=>Math.abs(r.d-records[0].d)<Math.max(1e-6,records[0].d*.002));
    let successive=null,successivePairs=[];
    if(equalD){const half=Math.floor(points.length/2);for(let i=0;i<half;i++){const j=i+half;if(j<points.length){const N=points[j][0]-points[i][0],d=points[j][1]-points[i][1];successivePairs.push({i,j,N,d});}}successive=2000*successivePairs.reduce((s,p)=>s+p.d,0)/successivePairs.reduce((s,p)=>s+p.N,0);}
    return{records,points,fit,fitMode:contiguous?'cumulative':'independent',lambdaFit,total,successive,successivePairs,reference,errorPercent:Math.abs((lambdaFit??total)-reference)/reference*100,totalN:cumN,totalD:cumD,contiguous};
  }
  function air(rows,lambda=632.8,L=60,p=101325,temp=20){
    lambda=number(lambda,'波长');L=number(L,'气室长度');p=number(p,'绝对气压');temp=number(temp,'温度');
    if(lambda<=0||L<=0||p<=0||temp<=-273.15)throw new Error('空气实验参数必须在有效物理范围内');
    const records=rows.filter(r=>r.enabled!==false).map((r,i)=>{const N=number(r.N,'第 '+(i+1)+' 次条纹数'),dp=number(r.dp,'压差');if(N<=0||dp<=0)throw new Error('条纹数与压差必须大于 0');const start=number(r.start,'起始时间'),end=number(r.end,'结束时间');if(start<0||end<=start)throw new Error('空气实验时间段无效');const delta=N*lambda*1e-9/(2*L*1e-3);return{...r,N,dp,start,end,delta,n:1+delta*p/(dp*1000)};});
    if(!records.length)return null;const mean=records.reduce((s,r)=>s+r.n,0)/records.length,sd=records.length>1?Math.sqrt(records.reduce((s,r)=>s+(r.n-mean)**2,0)/(records.length-1)):null,theory=1+2.8793*p/(1+.003671*temp)*1e-9;return{records,mean,sd,sem:sd===null?null:sd/Math.sqrt(records.length),theory,refractivityErrorPercent:Math.abs((mean-1)-(theory-1))/(theory-1)*100,lambda,L,p,temp};
  }
  function demo(){
    const wave=[];let t=0;const counts=[31.1,31.7,31.3,31.6,31.0,31.5,31.4,31.6];
    counts.forEach((N,i)=>{const end=t+8.1+(i%3)*.24;wave.push({id:'demo_w'+i,start:t,end,amount:1,unit:'turn',N,autoN:null,source:'simulated',enabled:true,note:'模拟演示：固定种子样例'});t=end;});
    const airRows=[{N:20.0,dp:39.8},{N:19.6,dp:39.3},{N:20.3,dp:40.1}].map((r,i)=>({...r,id:'demo_a'+i,start:i*22,end:i*22+20,source:'simulated',enabled:true,note:'模拟演示'}));
    const times=[],raw=[],clean=[],peaks=[];const rate=31.4/8.2;for(let i=0;i<=2100;i++){const s=i/30;times.push(s);clean.push(Math.cos(2*Math.PI*rate*s));raw.push(110+28*Math.cos(2*Math.PI*rate*s)+3*Math.sin(s*.3)+1.4*Math.sin(i*1.79));}for(let i=1;i/rate<70;i++)peaks.push(i/rate);
    return{wave,air:airRows,analysis:{times,raw,signal:clean,peaks,complete_cycles:peaks.length-1,valid_range:[peaks[0],peaks.at(-1)],source:'simulated',channel:'模拟',patch:0,warnings:['当前曲线和表格均为模拟演示数据，不是原视频测量结果。'],candidates:[],fps:30,frame_count:2101,start:0,end:70}};
  }
  function phaseBetween(analysis,start,end){
    if(!analysis||analysis.method!=='spatial')return analysis?countBetween(analysis.peaks,start,end):null;
    const a=number(start,'起始时间'),b=number(end,'结束时间');if(b<=a)throw new Error('结束时间须晚于起始时间');
    const times=analysis.times,phase=analysis.phase_cycles;if(!times?.length||!phase?.length||a<times[0]-1e-7||b>times.at(-1)+1e-7)return null;
    function at(t){let lo=0,hi=times.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(times[mid]<=t)lo=mid;else hi=mid;}return phase[lo]+(t-times[lo])/(times[hi]-times[lo])*(phase[hi]-phase[lo]);}
    return Math.abs(at(b)-at(a));
  }
  function turnDifference(first,last){const a=number(first,'起点累计圈次'),b=number(last,'终点累计圈次');if(a<0||b<=a)throw new Error('累计圈次应非负且随时间增加；重复或倒退的报数不能直接当作新一圈');return b-a;}
  return{calibration,number,displacement,interpolate,countBetween,phaseBetween,turnDifference,linearFit,wavelength,air,demo};
});
