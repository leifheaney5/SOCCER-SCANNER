"""Compose the Soccer Radar reel from recorded frames, cards and captions."""
import json
import os
import subprocess
import sys

reel = sys.argv[1]
out_path = sys.argv[2]
os.chdir(reel)
tl = json.load(open('timeline.json'))
scenes, frames = tl['scenes'], tl['frames']
main_len = round(sum(f['dur'] for f in frames), 3)

with open('main.ffconcat', 'w') as fh:
    fh.write('ffconcat version 1.0\n')
    for f in frames:
        fh.write(f"file '{f['name']}'\nduration {f['dur']:.4f}\n")
    fh.write(f"file '{frames[-1]['name']}'\n")

TITLE, END, XF = 2.9, 3.5, 0.5
order = ['home', 'scroll', 'tabs', 'search', 'details', 'filters', 'end']
caps = []
for i, key in enumerate(order[:-1]):
    start = scenes[key] + (0.35 if i else 0.6)
    stop = scenes[order[i + 1]] - (0.2 if order[i + 1] != 'end' else XF + 0.05)
    caps.append((f'c{i + 1}.png', round(start, 3), round(stop - start, 3)))

cmd = ['ffmpeg', '-v', 'error', '-y',
       '-loop', '1', '-framerate', '30', '-t', str(TITLE), '-i', 'title.png',
       '-f', 'concat', '-safe', '0', '-i', 'main.ffconcat',
       '-loop', '1', '-framerate', '30', '-t', str(END), '-i', 'end.png']
for name, _, dur in caps:
    cmd += ['-loop', '1', '-framerate', '30', '-t', str(dur), '-i', name]
cmd += ['-f', 'lavfi', '-t', '60', '-i', 'anullsrc=r=48000:cl=stereo']

g = [f'[1:v]fps=30,trim=duration={main_len},setpts=PTS-STARTPTS,setsar=1,format=rgba[m0]']
for i, (_, start, dur) in enumerate(caps):
    n = 3 + i
    g.append(f'[{n}:v]format=rgba,fade=in:st=0:d=0.3:alpha=1,fade=out:st={dur - 0.3:.3f}:d=0.3:alpha=1,'
             f'setpts=PTS-STARTPTS+{start}/TB[cap{i}]')
    g.append(f"[m{i}][cap{i}]overlay=x=0:y='1440+48*max(0\\,1-(t-{start})/0.35)':eval=frame:eof_action=pass[m{i + 1}]")
g.append('[0:v]fps=30,setsar=1,format=rgba,fade=in:st=0:d=0.4[t]')
g.append(f'[2:v]fps=30,setsar=1,format=rgba,fade=out:st={END - 0.6}:d=0.6[e]')
off1 = TITLE - XF
off2 = round(TITLE + main_len - XF - XF, 3)
g.append(f'[t][m{len(caps)}]xfade=transition=fade:duration={XF}:offset={off1}[a]')
g.append(f'[a][e]xfade=transition=fade:duration={XF}:offset={off2},scale=out_range=tv:out_color_matrix=bt709,format=yuv420p[v]')
total = round(off2 + END, 3)

cmd += ['-filter_complex', ';'.join(g), '-map', '[v]', '-map', f'{3 + len(caps)}:a',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
        '-r', '30', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-c:a', 'aac', '-b:a', '128k', '-t', str(total), '-movflags', '+faststart', out_path]
print('main', main_len, 'total', total)
for c in caps:
    print('caption', c)
subprocess.run(cmd, check=True)
