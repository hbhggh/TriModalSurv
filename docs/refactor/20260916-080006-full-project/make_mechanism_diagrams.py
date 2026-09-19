from pathlib import Path
import json,zlib,base64,html,re,copy
root=Path.cwd();b=Path(__file__).parent
src=(root/'experiments/I01_patient_retrieval/knowledge/method.excalidraw.svg').read_text();payload=json.loads(base64.b64decode(re.search(r'payload-start -->(.*?)<!-- payload-end',src,re.S)[1]));old=json.loads(zlib.decompress(payload['encoded'].encode('latin1')));template=old['elements'][0]
plans={
 'I02_population_prototypes':('I02 · 人群配对原型（已有 K8 机制）',['完整 train 患者：三模态特征','mean → projector → 256维编码','仅WSI做K-means；同簇配对均值','验证/测试：WSI余弦Top-1补缺侧','NPJ-C 融合 → 生存输出'],'每轮覆盖更新原型；训练前向不补偿。只使用 train 建库。'),
 'I03_npj_d_dm_e1':('I03 · 历史 D / Dm / 旧 E1 对照',['D：原特征 → mean → projector','D：模态等权融合 → 单token骨架','Dm：先用train原始特征均值补缺','旧E1：NPJ-C + CAPRecall','分别保留预测与原风险评估口径'],'历史对照身份保持；D/Dm与旧E1不能按一个补偿机制解释。'),
 'I04_cap4_multi_prototypes':('I04 · 已有 D 版时间箱内多原型',['train_quantile：仅train拟合时间箱','每个时间箱初始化 L 个有效原型','训练：最近有效槽 EMA 更新','缺失：WSI查询温度注意力召回','D 模态均值融合 → 生存输出'],'只整理已存在 D 版；C 版未在本轮实现或实验。')}
checks=[]
for exp,(title,labels,note) in plans.items():
 els=[];svg=['<rect width="1120" height="730" fill="#fafcff"/>']
 for i,text in enumerate([title,*labels,note]):
  el=copy.deepcopy(template);el.update(id=f'text-{i}',text=text,originalText=text,x=60,y=35+i*90,width=1000,height=42,fontSize=26 if i==0 else 23,seed=i+1,versionNonce=100+i);els.append(el)
  svg.append(f'<text x="60" y="{65+i*90}" font-family="sans-serif" font-size="{el["fontSize"]}" fill="#24384b">{html.escape(text)}</text>')
  if 1<=i<5:
   # 可编辑的独立向下箭头文本，和SVG显示一致。
   e=copy.deepcopy(el);e.update(id=f'arrow-{i}',text='↓',originalText='↓',x=75,y=el['y']+43,width=30,height=36);els.append(e)
   svg.append(f'<text x="75" y="{el["y"]+72}" font-family="sans-serif" font-size="23" fill="#416b91">↓</text>')
 scene={'type':'excalidraw','version':2,'source':'https://excalidraw.com','elements':els,'appState':{'viewBackgroundColor':'#fafcff','gridSize':None},'files':{}}
 encoded=base64.b64encode(json.dumps({'version':'1','encoding':'bstring','compressed':True,'encoded':zlib.compress(json.dumps(scene,ensure_ascii=False).encode()).decode('latin1')}).encode()).decode()
 text='<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="730" viewBox="0 0 1120 730">\n<!-- svg-source:excalidraw -->\n<metadata><!-- payload-type:application/vnd.excalidraw+json --><!-- payload-version:2 --><!-- payload-start -->'+encoded+'<!-- payload-end --></metadata>\n'+'\n'.join(svg)+'\n</svg>\n'
 p=root/'experiments'/exp/'knowledge/method.excalidraw.svg'
 with p.open('x') as f:f.write(text)
 parsed=json.loads(base64.b64decode(re.search(r'payload-start -->(.*?)<!-- payload-end',p.read_text(),re.S)[1]));assert json.loads(zlib.decompress(parsed['encoded'].encode('latin1')))==scene
 checks.append({'path':str(p.relative_to(root)),'editable_scene_roundtrip':True,'elements':len(els),'native_editor_tested':False})
(b/'diagram-scene-verification.json').write_text(json.dumps(checks,indent=2))
