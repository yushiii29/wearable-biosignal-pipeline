"""实验性心电片段估计。原始 ADC 不变；质量标记不判断人的状态或疾病。"""
import numpy as np

ALGORITHM = 'ecg_segments_v1'
MIN_SECONDS = 5.0
WINDOW_SECONDS = 6.0


def _peaks(t, y, polarity):
    """局部中位数去基线，仅供找峰；不覆盖原始波形或保存数据。"""
    fs = 1 / float(np.median(np.diff(t)))
    width = max(3, int(round(.20 * fs)) | 1)
    padded = np.pad(y, width//2, mode='edge')
    baseline = np.median(np.lib.stride_tricks.sliding_window_view(padded, width), axis=1)
    residual = (y-baseline)*polarity
    # 约12ms的均值只用于检测，抑制高频细纹；实际波形仍完整保留。
    smooth = max(1, int(round(.012*fs)) | 1)
    z = np.convolve(np.pad(residual, smooth//2, mode='edge'),
                    np.ones(smooth)/smooth, mode='valid')
    noise = float(np.median(np.abs(z-np.median(z))))*1.4826
    threshold = max(25.0, 5.0*noise, .30*float(np.percentile(z, 99.5)))
    candidates = np.flatnonzero((z[1:-1]>z[:-2]) & (z[1:-1]>=z[2:]) & (z[1:-1]>threshold))+1
    peaks = []
    for i in candidates:
        if not peaks or t[i]-t[peaks[-1]] >= .30:
            peaks.append(int(i))
        elif z[i]>z[peaks[-1]]:
            peaks[-1] = int(i)
    return peaks, threshold, noise


def _window(t, y, polarity, origin, lo, hi):
    result = {'start_s':round(float(t[0]-origin),3), 'end_s':round(float(t[-1]-origin),3),
              'sample_start':int(lo), 'sample_end_exclusive':int(hi),
              'sample_count':int(len(t)), 'bpm':None, 'candidate_bpm':None,
              'accepted':False, 'reasons':[]}
    dt = np.diff(t)
    result['rail_fraction'] = round(float(np.mean((y<=2)|(y>=4093))),6)
    result['peak_count'] = 0
    if t[-1]-t[0] < MIN_SECONDS-.025:
        result['reasons'].append('The segment is shorter than about 5 seconds.')
    if len(dt)==0 or np.any(dt<=0) or np.max(dt)>.1:
        result['reasons'].append('Timestamps repeat, go backwards, or contain a sampling gap.')
        return result
    result['effective_hz'] = round(float((len(t)-1)/(t[-1]-t[0])),3)
    if 1/np.median(dt)<100:
        result['reasons'].append('Effective sampling rate is below 100 Hz.')
        return result
    if result['rail_fraction']>.02:
        result['reasons'].append('Excessive clipping in the segment.')
    if np.ptp(y)<50:
        result['reasons'].append('Insufficient signal amplitude in the segment.')
        return result
    peaks, threshold, noise = _peaks(t,y,polarity)
    result.update(peak_count=len(peaks), peak_times_s=[round(float(t[i]-origin),4) for i in peaks],
                  detection_threshold_adc=round(threshold,3), noise_estimate_adc=round(noise,3))
    if len(peaks)<4:
        result['reasons'].append('Fewer than 4 usable candidate peaks were found.')
        return result
    rr = np.diff(t[peaks])
    result['candidate_bpm'] = round(60/float(np.median(rr)),1)
    result['rr_cv'] = round(float(np.std(rr)/np.mean(rr)),5)
    if np.any((rr<.30)|(rr>2)):
        result['reasons'].append('Candidate peak intervals are outside the estimation range of this prototype.')
    if result['rr_cv']>.20:
        result['reasons'].append('Candidate peak intervals vary substantially; manual review is required.')
    if not result['reasons']:
        result['accepted'] = True
        result['bpm'] = result['candidate_bpm']
    return result


def analyze_ecg(rows, polarity=1):
    """返回可序列化分析；优先整段，否则使用最近的可估计窗口。

    这是启发式原型检查，不是信号质量认证，更不是健康/惊恐/心律诊断。
    不跨不连续窗口拼接RR，不插值或替换削波样本，不推算无信号时段心率。
    """
    result = {'algorithm':ALGORITHM, 'bpm':None, 'candidate_bpm':None,
              'status':'unavailable', 'scope':None, 'selected_window':None,
              'windows':[], 'polarity':int(polarity), 'sample_count':len(rows),
              'warning':'Experimental estimate, not verified against a reference device. Motion artefacts may also produce repeated false peaks.',
              'explanation':''}
    if polarity not in (-1,1):raise ValueError('Peak polarity must be 1 or -1.')
    if len(rows)<2:
        result['explanation']='The recording is too short to estimate heart rate.'
        return result
    try:
        t = np.asarray([r['t_ms']/1000 for r in rows],float)
        y = np.asarray([r['ecg_adc'] for r in rows],float)
    except (KeyError,TypeError,ValueError):
        result['explanation']='Valid ECG fields are missing.'
        return result
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)) or np.any((y<0)|(y>4095)):
        result['explanation']='Raw data contains non-finite or out-of-range values.'
        return result
    if np.any(np.diff(t)<=0):
        result['explanation']='Timestamps repeat or go backwards; a reliable estimate is not possible.'
        return result
    result['duration_s']=round(float(t[-1]-t[0]),3)
    result['rail_fraction']=round(float(np.mean((y<=2)|(y>=4093))),6)
    if t[-1]-t[0]<MIN_SECONDS-.025:
        result['explanation']='At least about 5 seconds of signal is required. No default or simulated heart rate will be inserted.'
        return result
    whole = _window(t,y,polarity,t[0],0,len(t))
    result['whole_record']=whole
    result['candidate_bpm']=whole['candidate_bpm']
    # 保留每个窗口结果，便于批量分析时区分片段估计与整段估计。
    start_offsets = list(np.arange(0,max(0,t[-1]-t[0]-WINDOW_SECONDS),1.0))
    start_offsets.append(max(0,float(t[-1]-t[0])-WINDOW_SECONDS))
    for offset in sorted(set(round(float(v),6) for v in start_offsets)):
        lo = int(np.searchsorted(t,t[0]+offset,side='left'))
        hi = int(np.searchsorted(t,t[0]+offset+WINDOW_SECONDS+.000001,side='right'))
        if hi-lo>=2:
            result['windows'].append(_window(t[lo:hi],y[lo:hi],polarity,t[0],lo,hi))
    passed = [window for window in result['windows'] if window['accepted']]
    result['accepted_window_count']=len(passed)
    result['window_count']=len(result['windows'])
    if whole['accepted']:
        selected=whole
        result.update(status='estimated_full',scope='full')
        result['explanation']='Whole-recording estimate; candidate peaks still require manual checking.'
    elif passed:
        selected=passed[-1]
        result.update(status='estimated_partial',scope='segment')
        result['explanation']='The latest estimable segment is used. It is not the average heart rate of the whole recording; all other segments are fully preserved.'
    else:
        result['explanation']='No segment passed the prototype checks in this recording; '+', '.join(whole['reasons'])
        # 没有可估计心率时，候选峰频率仅作诊断留痕，绝不冒充有效心率。
        return result
    result['bpm']=selected['bpm']
    result['selected_window']=selected
    return result


def format_ecg_analysis(result, source='DEVICE'):
    if result['bpm'] is not None:
        selected=result['selected_window']
        scope='whole recording' if result['scope']=='full' else 'segment'
        text=(f"{source} heart-rate estimate: {result['bpm']} BPM ({scope}, after capture start: {selected['start_s']:.1f}–{selected['end_s']:.1f} s); {result['explanation']}")
    else:
        text='No usable heart-rate estimate for this recording; '+result['explanation']
        if result.get('candidate_bpm') is not None:
            text+=f"; candidate peak rate: {result['candidate_bpm']} per minute (may include motion or interference peaks; not a valid heart rate)"
    return text+'; '+result['warning']
