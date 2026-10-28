import { useEffect, useState } from 'react';
import { favoriteImage, downloadImage, listFavoriteImages, getImageVisionStatus, analyzeImageVision,
  type ResearchImage, type ResearchRun, type VisualObservation, type VisualGroup, type VisualReport } from '../api/research';

export function ImageGallery({ images, onFavorite, onDownload, busyId, observations={} }: {
  images: ResearchImage[]; onFavorite?: (image: ResearchImage) => void;
  onDownload?: (image: ResearchImage) => void; busyId?: number | null;
  observations?:Record<number,VisualObservation>;
}) {
  const fitLabels={MATCH:'符合用途',PARTIAL:'部分可借鉴',NOT_MATCH:'关联较弱'};
  return <div className="image-reference-grid">{images.map(image => {
    const observation=observations[image.id];
    return <article className="image-reference-card" key={image.id}>
    <a className="image-reference-preview" href={image.source_url} target="_blank" rel="noopener noreferrer">
      <img src={image.thumbnail_url} alt={image.title} loading="lazy" referrerPolicy="no-referrer"
        onError={event => { event.currentTarget.style.visibility = 'hidden'; }} />
      <span>打开原站看图 ↗</span>
    </a>
    <div className="image-reference-body">
      <div className="image-reference-meta"><span>{image.provider==='filmgrab' ? 'FilmGrab · 电影参考' : 'Openverse · 图片参考'}</span>
        <span>{image.width && image.height ? `${image.width} × ${image.height}` : '尺寸未知'}</span></div>
      <p className="notice">{observation?.readable ? `已看图 · ${fitLabels[observation.fit]}` : image.recommended ? '用途推荐 · 元数据判断' : '待看图确认'}</p>
      <h4>{image.title}</h4>
      <p className="notice">{image.creator || '作者未标明'} · {image.license_url
        ? <a href={image.license_url} target="_blank" rel="noopener noreferrer">{image.license.toUpperCase() || '查看许可'}</a>
        : '参考预览 · 成片使用授权待确认'}</p>
      {observation?.readable ? <><p>{observation.description}</p>
        <details className="visual-image-details"><summary>画面分析与用途</summary>
          <p><strong>场景：</strong>{observation.scene}</p><p><strong>光线：</strong>{observation.lighting}</p>
          <p><strong>色彩：</strong>{observation.colors.join('、')}</p><p><strong>构图：</strong>{observation.composition}</p>
          <p>{observation.purpose_relevance}</p><p>{observation.suggestion}</p>
          {observation.uncertainty && <p className="notice">待确认：{observation.uncertainty}</p>}
        </details></> : image.reason && <p>{image.reason}</p>}
      <details><summary>用途建议与署名</summary>
        {image.usage_notes && <p>{image.usage_notes}</p>}
        <p className="notice">{image.attribution || '请在原站核对作者与署名要求。'}</p>
      </details>
      <div className="image-reference-actions">
        <button type="button" aria-pressed={image.favorite} disabled={busyId != null}
          onClick={() => onFavorite?.(image)}>{image.favorite ? '已收藏' : '收藏'}</button>
        {image.provider==='filmgrab' ? <span className="notice">原站参考预览</span> :
          <button type="button" disabled={busyId != null || !image.license_url || !image.license}
            onClick={() => onDownload?.(image)}>{busyId===image.id ? '处理中…' : image.downloaded ? '再次下载' : '下载原图'}</button>}
      </div>
    </div>
  </article>;})}</div>;
}

function VisualRegion({group,images,observations,onFavorite,onDownload,busyId}:{group:VisualGroup;
  images:ResearchImage[];observations:Record<number,VisualObservation>;onFavorite:(image:ResearchImage)=>void;
  onDownload:(image:ResearchImage)=>void;busyId:number|null}) {
  const [expanded,setExpanded]=useState(false);
  const rows=group.image_ids.flatMap(id=>images.filter(image=>image.id===id));
  return <section className="visual-reference-region" aria-label={group.category}>
    <header><span className="eyebrow">{rows.length} 张参考</span><h3>{group.category}</h3>
      <p>{group.summary}</p><ul>{group.key_points.map(point=><li key={point}>{point}</li>)}</ul>
      {group.suggested_action && <p className="notice">创作建议：{group.suggested_action}</p>}</header>
    <ImageGallery images={expanded?rows:rows.slice(0,2)} observations={observations} busyId={busyId}
      onFavorite={onFavorite} onDownload={onDownload}/>
    {rows.length>2 && <button className="visual-expand" type="button" onClick={()=>setExpanded(!expanded)}>
      {expanded?'收起本区':`展开其余 ${rows.length-2} 张`}</button>}
  </section>;
}

export function VisualReferenceGroups({report,images,onFavorite=()=>{},onDownload=()=>{},busyId=null}:{
  report:VisualReport;images:ResearchImage[];onFavorite?:(image:ResearchImage)=>void;
  onDownload?:(image:ResearchImage)=>void;busyId?:number|null}) {
  const observations=Object.fromEntries(report.observations.filter(row=>row.readable).map(row=>[row.image_id,row]));
  const excluded=images.filter(image=>observations[image.id]?.fit==='NOT_MATCH');
  const unread=images.filter(image=>!observations[image.id]);
  return <div className="visual-reference-groups">
    <div className="research-overview"><span className="eyebrow">看图筛选与创作归纳</span><h3>这组画面可以怎样启发创作</h3>
      <p>{report.overview}</p><p className="notice">已分析 {report.analyzed_count}/{report.candidate_count} 张预览 · {report.model} · {new Date(report.analyzed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）</p></div>
    {report.groups.map(group=><VisualRegion key={group.category} group={group} images={images}
      observations={observations} onFavorite={onFavorite} onDownload={onDownload} busyId={busyId}/>)}
    {!report.groups.length && <p className="research-empty">这组预览与当前用途的关联较弱，可展开候选查看原因，或调整检索方向。</p>}
    {excluded.length>0 && <details className="visual-other-images"><summary>与当前用途关联较弱 · {excluded.length} 张</summary>
      <ImageGallery images={excluded} observations={observations} onFavorite={onFavorite} onDownload={onDownload} busyId={busyId}/></details>}
    {unread.length>0 && <details className="visual-other-images"><summary>尚未完成看图 · {unread.length} 张</summary>
      <ImageGallery images={unread} onFavorite={onFavorite} onDownload={onDownload} busyId={busyId}/></details>}
  </div>;
}

export function ImageEmptyState({run}:{run:ResearchRun}) {
  const failed=run.status==='FAILED' || (run.errors ?? []).length>0;
  return <div className="research-empty">
    <p>{failed ? '本次图片检索未完成，请查看上方的具体原因。来源请求失败不代表没有相关图片。' :
      '所选来源本次没有返回可用图片，这不代表全网没有相关素材。'}</p>
    {!failed && <p>Openverse 可从核心画面题材检索；FilmGrab 按片名、导演或摄影师查找。可在“调整参考来源”中选择范围。</p>}
    {!run.image_summary && <p>此历史结果未记录具体检索词；重新运行后会显示实际检索词和各次返回数量。</p>}
  </div>;
}

export function ImageResults({ run }: { run: ResearchRun }) {
  const [images, setImages] = useState(run.images ?? []);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<ResearchImage[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [visual,setVisual]=useState<VisualReport|null>(run.visual_analysis??null);
  const [visionStatus,setVisionStatus]=useState<{configured:boolean;model:string|null}|null>(null);
  const [visionBusy,setVisionBusy]=useState(false);
  const [notice,setNotice]=useState('');
  useEffect(() => { setImages(run.images ?? []); setFavoritesOnly(false); setFavorites([]); setError('');
    setVisual(run.visual_analysis??null);setNotice(''); }, [run]);
  useEffect(()=>{const controller=new AbortController();
    getImageVisionStatus(controller.signal).then(setVisionStatus).catch(()=>{});
    return ()=>controller.abort();},[]);
  async function analyzeVisuals() {
    setVisionBusy(true);setError('');setNotice('');
    try {const result=await analyzeImageVision(run.plan_id,run.id);setVisual(result);setFavoritesOnly(false);
      setNotice(result.cached?'图片与目的未变，已复用保存的看图结果。':'看图筛选与分类归纳已保存。');}
    catch(reason){setError(reason instanceof Error?reason.message:'看图分析未完成。');}
    finally {setVisionBusy(false);}
  }
  async function toggleFavorites() {
    if (favoritesOnly) { setFavoritesOnly(false); return; }
    try { setFavorites(await listFavoriteImages(run.plan_id)); setFavoritesOnly(true); setError(''); }
    catch { setError('暂时无法加载收藏，请重试。'); }
  }
  async function saveFavorite(image: ResearchImage) {
    setBusyId(image.id); setError('');
    try {
      await favoriteImage(image.id, !image.favorite);
      setImages(current => current.map(row => row.id === image.id ? { ...row, favorite: !image.favorite } : row));
      setFavorites(current => current.filter(row => row.id !== image.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : '收藏未保存。'); }
    finally { setBusyId(null); }
  }
  async function saveFile(image: ResearchImage) {
    setBusyId(image.id); setError('');
    try {
      await downloadImage(image.id);
      setImages(current => current.map(row => row.id === image.id ? { ...row, downloaded: true } : row));
      setFavorites(current => current.map(row => row.id === image.id ? { ...row, downloaded: true } : row));
    } catch (reason) { setError(reason instanceof Error ? reason.message : '下载未完成。'); }
    finally { setBusyId(null); }
  }
  const visible = favoritesOnly ? favorites : images;
  const reportOnly=run.image_summary?.kind==='search';
  const observations=Object.fromEntries((visual?.observations??[]).filter(row=>row.readable).map(row=>[row.image_id,row]));
  return <section className="image-reference-results" aria-label="图片参考素材">
    {!visual && run.image_summary && <div className="research-overview"><span className="eyebrow">{reportOnly ? '检索记录' : '素材助手'}</span>
      <h3>{reportOnly ? '本次检索情况' : '这些图片线索可以怎样用'}</h3><p>{run.image_summary.overview}</p>
      {reportOnly && <p className="notice">{run.image_summary.limitations}</p>}</div>}
    <div className="section-heading"><h3>图片参考</h3><div className="research-actions">
      {images.length>0 && <button type="button" disabled={visionBusy || !visionStatus?.configured || run.status==='RUNNING'}
        onClick={()=>void analyzeVisuals()}>{visionBusy?'正在看图与归纳…':visual?'更新看图分析':'看图筛选与归纳'}</button>}
      <button type="button" aria-pressed={favoritesOnly} onClick={() => void toggleFavorites()}>{favoritesOnly ? '查看本次参考' : '本方案收藏'}</button></div></div>
    <p className="notice">{visual?'已有看图结果；预览分辨率可能限制判断，不代表已核实原图质量、使用授权或视频节奏。':'当前推荐依据是标题、标签或电影主创信息，尚未进行看图判断。点击“看图筛选与归纳”后，将使用 Qwen 分析最多12张公开预览。'}预览保留原有水印；参考不等于可用于成片。</p>
    {visionStatus && !visionStatus.configured && <p className="notice">视觉模型尚未配置，已保存的参考仍可预览和收藏。</p>}
    {notice && <p role="status" className="notice">{notice}</p>}
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {visual && !favoritesOnly ? <VisualReferenceGroups report={visual} images={images} busyId={visionBusy?-1:busyId}
      onFavorite={image=>void saveFavorite(image)} onDownload={image=>void saveFile(image)}/> : visible.length ?
      <ImageGallery images={visible} observations={observations} busyId={visionBusy?-1:busyId} onFavorite={image => void saveFavorite(image)}
        onDownload={image => void saveFile(image)} /> : favoritesOnly ? <p className="research-empty">本方案还没有收藏图片。</p> : <ImageEmptyState run={run}/>}
    {run.image_summary && !reportOnly && <details className="research-evidence"><summary>{visual?'原始检索与元数据分析':'检索范围与限制'}</summary><p>{run.image_summary.limitations}</p></details>}
  </section>;
}
