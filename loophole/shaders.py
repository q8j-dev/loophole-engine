import json
from pathlib import Path

from .geo import GW, TPV

_M = json.loads((Path(__file__).resolve().parent / "data" / "atlas" / "materials.json").read_text(encoding="utf-8"))
ATLAS_W, ATLAS_H, CELL_W, CELL_H, COLS, S = _M["ATLAS_W"], _M["ATLAS_H"], _M["CELL_W"], _M["CELL_H"], _M["COLS"], _M["S"]
LAYOUT = [tuple(x) for x in _M["LAYOUT"]]
ATLAS_H2 = json.loads((Path(__file__).resolve().parent / "data" / "atlas" / "materials2.json").read_text(encoding="utf-8"))["ATLAS_H"]
ATLAS_H3 = json.loads((Path(__file__).resolve().parent / "data" / "atlas" / "materials3.json").read_text(encoding="utf-8"))["ATLAS_H"]

HEAD = "precision highp float;\n"

CAM_U = """
uniform vec3 uCP;
uniform vec3 uCR;
uniform vec3 uCU;
uniform vec3 uCF;
uniform vec4 uProj;
uniform vec4 uVP;
uniform vec2 uJit;
"""

PROJECT = """
vec4 project(vec3 w) {
  vec3 r = w - uCP;
  float d = dot(r, uCF);
  vec2 xy = vec2(dot(r, uCR) * uProj.x, -dot(r, uCU) * uProj.y);
  return vec4((xy + uJit * d) * uVP.xy + uVP.zw * d, (d * (uProj.w + uProj.z) - 2.0 * uProj.w * uProj.z) / (uProj.w - uProj.z), d);
}
"""

GATE = """
uniform vec4 uWin;
uniform vec4 uClip;
uniform vec2 u_res;
void gate(vec3 w) {
  vec2 s = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  if (s.x < uWin.x || s.y < uWin.y || s.x > uWin.z || s.y > uWin.w) discard;
  if (dot(w, uClip.xyz) < uClip.w) discard;
}
"""

ENC = """
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec4 enc(vec3 c, float a) {
  float n = hash12(gl_FragCoord.xy + fract(u_timer * 7.13) * 91.7) - 0.5;
  return vec4(sqrt(clamp(c * 0.25, 0.0, 1.0)) + n / 255.0, a);
}
vec3 dec(vec3 e) { return e * e * 4.0; }
"""

NOISE = """
float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash12(i);
  float b = hash12(i + vec2(1.0, 0.0));
  float c = hash12(i + vec2(0.0, 1.0));
  float d = hash12(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
"""


def atlas_glsl(levels=None, cell_w=CELL_W, cell_h=CELL_H, atlas_w=ATLAS_W, h1=ATLAS_H, h2=ATLAS_H2, h3=ATLAS_H3):
    levels = levels or LAYOUT
    mi = ["vec3 mipInfo(float l) {"]
    for i, (x, y, s) in enumerate(levels[:-1]):
        mi.append(f"  if (l < {i}.5) return vec3({x}.0, {y}.0, {s}.0);")
    x, y, s = levels[-1]
    mi.append(f"  return vec3({x}.0, {y}.0, {s}.0);")
    mi.append("}")
    top = len(levels) - 1
    return f"""
uniform sampler2D uAtlas;
{chr(10).join(mi)}
vec3 tap(float cid, vec2 uv, float l) {{
  vec3 mi = mipInfo(l);
  vec2 cell = vec2(mod(cid, {COLS}.0) * {cell_w}.0, floor(cid / {COLS}.0 + 0.001) * {cell_h}.0);
  vec2 f = fract(uv);
  vec2 p = cell + mi.xy + vec2(f.x, 1.0 - f.y) * mi.z;
  return texture2D(uAtlas, p / vec2({atlas_w}.0, {h1}.0)).rgb;
}}
vec3 samp(float cid, vec2 uv, float lod) {{
  float l0 = floor(lod);
  return mix(tap(cid, uv, l0), tap(cid, uv, min(l0 + 1.0, {top}.0)), lod - l0);
}}
uniform sampler2D uAtlas2;
uniform sampler2D uAtlas3;
vec3 tapB(float atl, float cid, vec2 uv, float l) {{
  vec3 mi = mipInfo(l);
  vec2 cell = vec2(mod(cid, {COLS}.0) * {cell_w}.0, floor(cid / {COLS}.0 + 0.001) * {cell_h}.0);
  vec2 f = fract(uv);
  vec2 p = cell + mi.xy + vec2(f.x, 1.0 - f.y) * mi.z;
  if (atl < 2.5) return texture2D(uAtlas2, p / vec2({atlas_w}.0, {h2}.0)).rgb;
  return texture2D(uAtlas3, p / vec2({atlas_w}.0, {h3}.0)).rgb;
}}
vec3 sampA(float atl, float cid, vec2 uv, float lod) {{
  if (atl < 1.5) return samp(cid, uv, lod);
  float l0 = floor(lod);
  return mix(tapB(atl, cid, uv, l0), tapB(atl, cid, uv, min(l0 + 1.0, {top}.0)), lod - l0);
}}
"""


ATLAS = atlas_glsl()

WIND = """
uniform vec4 uWind;
float gust(vec2 p, float t) {
  vec2 d = uWind.xy;
  float a = dot(p, d) * 0.11 - t * 1.25;
  float b = dot(p, vec2(-d.y, d.x)) * 0.05 + t * 0.21;
  float g = 0.5 + 0.5 * sin(a + sin(b) * 1.7);
  g *= 0.65 + 0.35 * sin(a * 0.37 + 1.3 + b * 2.1);
  return g * g;
}
vec3 windAt(vec3 p, float t, float ph) {
  float g = gust(p.xz, t);
  float base = uWind.z * (0.35 + 0.65 * g);
  float flut = sin(t * 2.3 + ph) * 0.35 + sin(t * 3.7 + ph * 1.7) * 0.2;
  vec2 lat = vec2(-uWind.y, uWind.x) * sin(t * 1.1 + ph * 0.8) * 0.3;
  vec2 h = uWind.xy * (base * (1.0 + flut * 0.4)) + lat * uWind.z * (0.3 + g);
  return vec3(h.x, -0.15 * dot(h, h), h.y);
}
"""


WORLD_VS = HEAD + CAM_U + PROJECT + WIND + """
attribute float aI;
uniform float u_timer;
uniform sampler2D uGeo;
uniform vec4 uGeoI;
uniform vec4 uGeoP;
uniform vec3 uMP;
uniform vec3 uMX;
uniform vec3 uMY;
uniform vec3 uMZ;
uniform vec4 uMode;
varying vec3 vW;
varying vec3 vN;
varying vec3 vMP;
varying vec3 vMN;
varying vec2 vLM;
varying float vMat;
varying float vAO;
varying float vSeed;
varying float vBA;
varying vec4 vIrr;
varying vec3 vTan;
uniform vec4 uSkin;
uniform vec4 uLOD;
uniform vec4 uTerr;
uniform vec4 uWind2;
uniform vec4 uBM[96];
uniform vec4 uSk0;
uniform vec4 uSk1;
uniform vec4 uSk2;
vec3 rx(vec3 p, vec2 c, float a) {
  float s = sin(a);
  float co = cos(a);
  vec2 q = p.yz - c;
  return vec3(p.x, c.x + q.x * co - q.y * s, c.y + q.x * s + q.y * co);
}
float gvid;
vec3 gtt(float t) {
  float row = floor((t + 0.5) / """ + f"{GW}.0" + """);
  float col = t - row * """ + f"{GW}.0" + """;
  return floor(texture2D(uGeo, vec2((col + 0.5) / """ + f"{GW}.0" + """, (row + 0.5) * uGeoI.z)).rgb * 255.0 + 0.5);
}
vec3 gt(float k) {
  return gtt(k * (uGeoI.w / """ + f"{TPV}.0" + """) + gvid);
}
void main() {
  if (aI >= uGeoI.y) {
    gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
    return;
  }
  vec3 ixv = gtt(uGeoI.w + uGeoI.x + aI);
  gvid = ixv.r * 65536.0 + ixv.g * 256.0 + ixv.b;
  vec3 ta = gt(0.0);
  vec3 tb = gt(1.0);
  vec3 t5 = gt(5.0);
  vec3 aPos = (ta * 256.0 + tb) / 65535.0 * uGeoP.w + uGeoP.xyz;
  vTan = gt(7.0) / 255.0 * 2.0 - 1.0;
  float lodk = 1.0;
  if (t5.z > 4.5 && t5.z < 7.5 && uLOD.x > 0.0) {
    vec3 lw = uMP + uMX * aPos.x + uMY * aPos.y + uMZ * aPos.z;
    float ld = length(lw - uCP);
    vec3 hk = t5.z > 5.5 ? aPos : vTan * 13.0 + floor(aPos * 0.7);
    float hh = fract(sin(dot(floor(hk * 61.0), vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    float fd = smoothstep(uLOD.x, uLOD.x + uLOD.y, ld);
    if (t5.z > 6.5) {
      if (hh < fd) {
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
        return;
      }
    } else if (t5.z > 5.5) {
      lodk = mix(1.0, 0.35, fd);
    } else {
      float kp = clamp(1.0 - (ld - uLOD.x * 1.5) / (uLOD.y * 1.6), 0.4, 1.0);
      if (hh > kp) {
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
        return;
      }
    }
  }
  vec3 tn = gt(2.0);
  vec3 tc = gt(3.0);
  vec3 td = gt(4.0);
  vSeed = t5.x;
  vec3 t6 = gt(6.0) / 255.0;
  vIrr = vec4(t6 * t6 * 4.0, t5.z);
  vec3 aNrm = tn / 255.0 * 2.0 - 1.0;
  vLM = vec2(tc.x * 256.0 + tc.y, tc.z * 256.0 + td.x) / 65535.0;
  vMat = td.y;
  vAO = td.z / 255.0;
  float ba = 0.0;
  if (uSkin.x > 1.5) {
    int bj = int(t5.y + 0.5) * 3;
    vec4 r0 = uBM[bj];
    vec4 r1 = uBM[bj + 1];
    vec4 r2 = uBM[bj + 2];
    vec4 hp = vec4(aPos, 1.0);
    aPos = vec3(dot(r0, hp), dot(r1, hp), dot(r2, hp));
    aNrm = normalize(vec3(dot(r0.xyz, aNrm), dot(r1.xyz, aNrm), dot(r2.xyz, aNrm)));
  } else if (uSkin.x > 0.5) {
    float b = t5.y;
    vec3 p = aPos;
    if (b > 0.5 && b < 2.5) {
      if (b > 1.5) { p = rx(p, vec2(0.5, -0.02), uSk0.y); ba += uSk0.y; }
      p = rx(p, vec2(0.9, 0.0), uSk0.x); ba += uSk0.x;
    } else if (b > 2.5 && b < 4.5) {
      if (b > 3.5) { p = rx(p, vec2(0.5, -0.04), uSk0.w); ba += uSk0.w; }
      p = rx(p, vec2(0.9, 0.0), uSk0.z); ba += uSk0.z;
    } else if (b > 4.5 && b < 6.5) {
      if (b > 5.5) { p = rx(p, vec2(1.15, 0.03), uSk1.y); ba += uSk1.y; }
      p = rx(p, vec2(1.42, 0.0), uSk1.x); ba += uSk1.x;
    } else if (b > 6.5 && b < 8.5) {
      if (b > 7.5) { p = rx(p, vec2(1.18, -0.06), uSk1.w); ba += uSk1.w; }
      p = rx(p, vec2(1.42, 0.0), uSk1.z); ba += uSk1.z;
    } else if (b > 8.5) {
      p = rx(p, vec2(1.5, 0.0), uSk2.x); ba += uSk2.x;
    }
    if (b < 0.5 || b > 4.5) { p = rx(p, vec2(0.95, 0.0), uSk2.y); ba += uSk2.y; }
    p.y += uSkin.y;
    aPos = p;
    float s = sin(ba);
    float co = cos(ba);
    aNrm = vec3(aNrm.x, aNrm.y * co - aNrm.z * s, aNrm.y * s + aNrm.z * co);
  }
  vBA = ba;
  vec3 w = uMP + uMX * aPos.x + uMY * aPos.y + uMZ * aPos.z;
  if (t5.z > 5.5 && t5.z < 7.5) {
    vec3 off = vTan * 2.5 * inversesqrt(lodk);
    float ra = fract(sin(dot(floor(w * 7.0), vec3(12.9898, 78.233, 37.719))) * 43758.5453) * 6.2831;
    vec2 ro = vec2(off.x * cos(ra) - off.y * sin(ra), off.x * sin(ra) + off.y * cos(ra));
    w += uCR * ro.x + uCU * ro.y;
    vTan = -uCF;
  }
  if (t5.z > 4.5 && t5.z < 7.5) {
    float sw = vAO;
    vAO = 1.0;
    vec3 tree = uMP;
    float ph = fract(sin(dot(floor(aPos * 1.2), vec3(12.9898, 78.233, 37.719))) * 43758.5453) * 6.2831;
    vec3 wt = windAt(tree, u_timer, tree.x * 0.3 + tree.z * 0.17);
    vec3 wc = windAt(w, u_timer * 1.6, ph);
    w += wt * (0.22 * sw) + wc * (0.06 * sw);
    w += vec3(sin(u_timer * 7.3 + ph * 3.0), sin(u_timer * 6.1 + ph * 2.0) * 0.6, cos(u_timer * 6.7 + ph * 2.5)) * (0.008 * sw * (0.3 + uWind.z));
  }
  vW = w;
  vN = uMX * aNrm.x + uMY * aNrm.y + uMZ * aNrm.z;
  vMP = aPos;
  vMN = aNrm;
  vec4 cp = project(w);
  if (uMode.z > 0.5) cp.z = (-1.0 + (cp.z / cp.w + 1.0) * 0.002) * cp.w;
  gl_Position = cp;
}
"""

WORLD_FS = HEAD + """
uniform vec4 uTerr;
uniform vec4 uWind2;
uniform float u_timer;
""" + GATE + ENC + NOISE + ATLAS + """
uniform vec3 uCP;
uniform vec4 uProj;
uniform sampler2D uLM;
uniform vec4 uMode;
uniform vec3 uA0;
uniform vec3 uA1;
uniform vec3 uA2;
uniform vec3 uA3;
uniform vec3 uA4;
uniform vec3 uA5;
uniform vec3 uMX;
uniform vec3 uMY;
uniform vec3 uMZ;
uniform vec4 uLt[24];
uniform float uLtN;
uniform vec4 uLd[24];
uniform vec4 uLc[24];
uniform vec4 uHaze;
uniform vec4 uLf[24];
uniform sampler2D uTLM;
uniform vec4 uTLMP;
uniform sampler2D uTHM;
uniform vec4 uTHP;
uniform vec4 uFog;
uniform vec4 uFogS;
uniform vec3 uFogSun;
uniform vec3 uSkyA;
uniform vec4 uSunC;
uniform vec4 uO1;
uniform vec4 uO2;
uniform vec4 uSC[4];
uniform vec4 uSX[4];
uniform vec4 uSY[4];
uniform float uShN;
uniform vec3 uEmit;
varying vec3 vW;
varying vec3 vN;
varying vec3 vMP;
varying vec3 vMN;
varying vec2 vLM;
varying float vMat;
varying float vAO;
varying float vSeed;
varying float vBA;
varying vec4 vIrr;
varying vec3 vTan;
uniform sampler2D uDA;
uniform sampler2D uDN;
uniform sampler2D uDR;
vec2 dmip(vec2 uv, float l) {
  uv = clamp(uv, 0.0002, 0.9998);
  if (l < 0.5) return vec2(uv.x, uv.y * (2.0 / 3.0));
  float s = exp2(-l);
  return vec2(1.0 - 2.0 * s + uv.x * s, 2.0 / 3.0 + uv.y * s * (2.0 / 3.0));
}
vec3 dsamp(sampler2D t, vec2 uv, float lod) {
  float l0 = floor(lod);
  return mix(texture2D(t, dmip(uv, l0)).rgb, texture2D(t, dmip(uv, min(l0 + 1.0, 7.0))).rgb, lod - l0);
}

uniform vec4 uGB;
uniform vec3 uCF;
void gbOut(vec3 w) {
  float d = dot(w - uCP, uCF);
  float v = clamp(d / 150.0, 0.0, 1.0) * 65535.0;
  float hi = floor(v / 256.0);
  float lo = floor(v - hi * 256.0);
  gl_FragColor = vec4(hi / 255.0, lo / 255.0, uGB.y, 1.0);
}

uniform sampler2D uHist;
uniform sampler2D uPGB;
uniform vec3 uPC;
uniform vec3 uPRr;
uniform vec3 uPU;
uniform vec3 uPF;
uniform vec4 uPP;
uniform vec4 uSSR;
vec3 pproj(vec3 p) {
  vec3 r = p - uPC;
  float d = dot(r, uPF);
  vec2 n = vec2(dot(r, uPRr) * uPP.x, -dot(r, uPU) * uPP.y) / max(d, 1e-3) + uPP.zw;
  return vec3(n * 0.5 + 0.5, d);
}
vec2 gdep(vec2 uv) {
  vec4 g = texture2D(uPGB, uv);
  return vec2((g.r * 65280.0 + g.g * 255.0) / 65535.0 * 150.0, g.b);
}
vec4 ssr(vec3 P, vec3 R) {
  float t = 0.08;
  float tp = 0.0;
  for (int i = 0; i < 16; i++) {
    vec3 s = pproj(P + R * t);
    if (s.z < 0.05 || s.x < 0.0 || s.x > 1.0 || s.y < 0.0 || s.y > 1.0) break;
    vec2 g = gdep(s.xy);
    float dd = s.z - g.x;
    if (g.x > 0.02 && g.y < 0.75 && dd > 0.0 && dd < 0.3 + t * 0.12) {
      float a = tp;
      float b = t;
      for (int k = 0; k < 5; k++) {
        float m = (a + b) * 0.5;
        vec3 sm = pproj(P + R * m);
        if (sm.z - gdep(sm.xy).x > 0.0) b = m; else a = m;
      }
      vec3 sb = pproj(P + R * b);
      vec2 e = min(sb.xy, 1.0 - sb.xy);
      float f = smoothstep(0.0, 0.08, min(e.x, e.y)) * (1.0 - smoothstep(10.0, 22.0, b));
      vec3 h = texture2D(uHist, sb.xy).rgb;
      return vec4(h * h * 4.0, f);
    }
    tp = t;
    t = t * 1.32 + 0.05;
  }
  return vec4(0.0);
}

uniform sampler2D uEnv;
uniform sampler2D uEnvB;
uniform sampler2D uEnvC;
uniform vec4 uEnvP;
uniform vec3 uBox0;
uniform vec3 uBox1;
vec2 envUV(vec3 d) {
  vec3 a = abs(d);
  vec2 nd;
  float f;
  if (a.x >= a.y && a.x >= a.z) {
    if (d.x > 0.0) { f = 0.0; nd = vec2(d.z, -d.y) / a.x; }
    else { f = 1.0; nd = vec2(-d.z, -d.y) / a.x; }
  } else if (a.y >= a.z) {
    if (d.y > 0.0) { f = 2.0; nd = vec2(d.x, d.z) / a.y; }
    else { f = 3.0; nd = vec2(d.x, -d.z) / a.y; }
  } else {
    if (d.z > 0.0) { f = 4.0; nd = vec2(-d.x, -d.y) / a.z; }
    else { f = 5.0; nd = vec2(d.x, -d.y) / a.z; }
  }
  nd = clamp(nd, -0.94, 0.94);
  float i = mod(f, 3.0);
  float j = floor(f / 3.0 + 0.01);
  vec2 ndc = nd * vec2(1.0 / 3.0, 0.5) + vec2(-1.0 + (2.0 * i + 1.0) / 3.0, -1.0 + (2.0 * j + 1.0) * 0.5);
  return ndc * 0.5 + 0.5;
}
vec3 envSample(vec3 d, float rough) {
  vec2 uv = envUV(d);
  vec3 a = texture2D(uEnv, uv).rgb;
  vec3 b = texture2D(uEnvB, uv).rgb;
  vec3 c = texture2D(uEnvC, uv).rgb;
  vec3 e = mix(mix(a, b, smoothstep(0.08, 0.35, rough)), c, smoothstep(0.35, 0.7, rough));
  return e * e * 4.0;
}
vec3 envBRDF(vec3 F0, float rough, float ndv) {
  vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
  vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
  vec4 r = rough * c0 + c1;
  float a004 = min(r.x * r.x, exp2(-9.28 * ndv)) * r.x + r.y;
  vec2 AB = vec2(-1.04, 1.04) * a004 + r.zw;
  return F0 * AB.x + AB.y;
}

uniform sampler2D uProp;
uniform vec4 uPR;
uniform vec2 uPAt;
vec3 mipP(float l, float s) {
  if (l < 0.5) return vec3(8.0, 8.0, s);
  if (l < 1.5) return vec3(s + 3.0 * 8.0, 8.0, s * 0.5);
  float x = s + 2.0 * 8.0;
  float y = s * 0.5 + 2.0 * 8.0;
  float k = s * 0.25;
  float hz = 1.0;
  for (int i = 2; i < 8; i++) {
    if (abs(float(i) - l) < 0.5) return vec3(x + 8.0, y + 8.0, k);
    x += hz * (k + 2.0 * 8.0);
    y += (1.0 - hz) * (k + 2.0 * 8.0);
    hz = 1.0 - hz;
    k *= 0.5;
  }
  return vec3(x + 8.0, y + 8.0, k);
}
vec3 tapP(float m, vec2 uv, float l) {
  float s = uPR.z;
  vec3 mi = mipP(l, s);
  vec2 p = vec2(uPR.x + m * (s * 1.5 + 4.0 * 8.0), uPR.y) + mi.xy + clamp(uv, 0.0, 1.0) * mi.z;
  return texture2D(uProp, p / uPAt).rgb;
}
vec3 sampP(float m, vec2 uv, float lod) {
  float l0 = floor(lod);
  return mix(tapP(m, uv, l0), tapP(m, uv, min(l0 + 1.0, 7.0)), lod - l0);
}


float hitSphere(vec3 ro, vec3 rd, float len, vec4 s) {
  vec3 oc = ro - s.xyz;
  float b = dot(oc, rd);
  float c = dot(oc, oc) - s.w * s.w;
  float h = b * b - c;
  if (h < 0.0) return 1.0;
  float t = -b - sqrt(h);
  return (t > 0.0 && t < len) ? 0.0 : 1.0;
}
float hitBox(vec3 ro, vec3 rd, float len, vec3 c, vec3 ax, vec3 ay, vec3 hs) {
  vec3 az = cross(ax, ay);
  vec3 o = ro - c;
  vec3 lo = vec3(dot(o, ax), dot(o, ay), dot(o, az));
  vec3 ld = vec3(dot(rd, ax), dot(rd, ay), dot(rd, az)) + vec3(1e-6);
  vec3 t1 = (-hs - lo) / ld;
  vec3 t2 = (hs - lo) / ld;
  vec3 tn = min(t1, t2);
  vec3 tf = max(t1, t2);
  float a = max(max(tn.x, tn.y), tn.z);
  float b = min(min(tf.x, tf.y), tf.z);
  return (b > max(a, 0.0) && a < len) ? 0.0 : 1.0;
}
float hitCap(vec3 p, vec3 rd, float len, vec3 a, vec3 b, float r) {
  vec3 ba = b - a;
  vec3 oa = p - a;
  float baba = dot(ba, ba);
  float bard = dot(ba, rd);
  float den = baba - bard * bard;
  float t = den > 1e-5 ? (bard * dot(ba, oa) - baba * dot(rd, oa)) / den : 0.0;
  t = clamp(t, 0.0, len);
  float s = clamp(dot(oa + rd * t, ba) / baba, 0.0, 1.0);
  vec3 q = a + ba * s;
  t = clamp(dot(q - p, rd), 0.0, len);
  vec3 d = p + rd * t - q;
  return dot(d, d) < r * r ? 0.0 : 1.0;
}
float dynVis(vec3 p, vec3 q) {
  vec3 d = q - p;
  float len = length(d);
  vec3 rd = d / len;
  float v = 1.0;
  if (uO1.w > 0.05) v *= hitCap(p, rd, len, uO1.xyz - vec3(0.0, 0.3, 0.0), uO1.xyz + vec3(0.0, 0.3, 0.0), 0.15) * hitCap(p, rd, len, uO2.xyz - vec3(0.0, 0.25, 0.0), uO2.xyz + vec3(0.0, 0.22, 0.0), 0.2) * hitSphere(p, rd, len, vec4(uO2.xyz + vec3(0.0, 0.47, 0.0), 0.12));
  for (int i = 0; i < 4; i++) {
    if (float(i) >= uShN) break;
    vec3 hs = vec3(uSX[i].w, uSY[i].w, uSC[i].w);
    vec3 oc = p - uSC[i].xyz;
    float b = dot(oc, rd);
    float r2 = dot(hs, hs);
    float h = b * b - dot(oc, oc) + r2;
    if (h > 0.0 && -b + sqrt(h) > 0.0 && -b - sqrt(h) < len) v *= hitBox(p, rd, len, uSC[i].xyz, uSX[i].xyz, uSY[i].xyz, hs);
  }
  return v;
}
float lprof(vec3 L, vec4 D4, vec4 C4) {
  float c = dot(-L, D4.xyz);
  return C4.w < -1.5 ? max(c, 0.0) : smoothstep(D4.w, C4.w, c);
}
uniform vec2 uCut;
vec3 haze(vec3 ro, vec3 rd, float len, float jit) {
  if (uHaze.x <= 0.0) return vec3(0.0);
  if (uCut.x > 0.5 && rd.y < -0.01 && ro.y > uCut.y) {
    float t0 = (ro.y - uCut.y) / -rd.y;
    ro += rd * t0;
    len = max(len - t0, 0.0);
  }
  float L = min(len, 45.0);
  float dt = L / 10.0;
  vec3 acc = vec3(0.0);
  for (int k = 0; k < 10; k++) {
    vec3 p = ro + rd * ((float(k) + jit) * dt);
    for (int i = 0; i < 8; i++) {
      if (float(i) >= uHaze.y) break;
      vec3 lv = uLt[i].xyz - p;
      float d2 = dot(lv, lv);
      vec3 l = lv * inversesqrt(d2);
      float ph = 0.6 + 0.9 * pow(max(dot(-rd, l) * -1.0 + 1.0, 0.0) * 0.5, 2.0);
      acc += uLc[i].rgb * lprof(l, uLd[i], uLc[i]) / (d2 + 2.5) * ph;
    }
  }
  return acc * dt * uHaze.x + uHaze.z * vec3(0.004, 0.0047, 0.006) * L * uHaze.x;
}

float occ(vec3 p, vec3 n, vec4 s) {
  vec3 r = s.xyz - p;
  float l2 = dot(r, r);
  float l = sqrt(l2);
  vec3 rd = r / l;
  float k = s.w * s.w / l2;
  return k * (max(dot(n, rd), 0.0) * 0.55 + smoothstep(0.35, 0.95, rd.y) * 0.75);
}

uniform vec2 uNF;
uniform vec3 uRim;
void main() {
  gate(vW);
  if (uCut.x > 0.5) {
    if (vW.y > uCut.y) discard;
    if (gl_FrontFacing) {
      vec3 cd = normalize(vW - uCP);
      vec3 cp = uCP + cd * ((uCP.y - uCut.y) / max(-cd.y, 0.05));
      if (uGB.x > 0.5) { gbOut(cp); return; }
      gl_FragColor = enc(vec3(0.0), 1.0);
      return;
    }
  }
  bool leaf = vIrr.w > 4.5 && vIrr.w < 7.5;
  if (vMat > 76.5 && vMat < 77.5) {
    vec2 bp = mod(floor(gl_FragCoord.xy), 4.0);
    float bay = mod(bp.x * 4.0 + bp.y * 13.0 + floor(u_timer * 60.0) * 5.0, 16.0) / 16.0;
    if (bay > 0.38) discard;
  }
  if (leaf) {
    float dl = length(uCP - vW);
    float alod = floor(clamp(log2(max(dl / (uProj.y * u_res.y * 0.5) * 480.0, 1e-4)), 0.0, 5.0) + 0.5);
    float al = texture2D(uDR, dmip(vLM, alod)).b;
    float face = abs(dot(normalize(vTan), (uCP - vW) / dl));
    float thr = mix(0.5, 1.01, 1.0 - smoothstep(0.05, 0.22, face));
    if (al < thr) discard;
    vec2 fp = mod(floor(gl_FragCoord.xy), 4.0);
    float fb = (mod(fp.x * 4.0 + fp.y * 13.0, 16.0) + 0.5) / 16.0;
    if (fb > smoothstep(uNF.x, uNF.y, dl)) discard;
  }
  if (uGB.x > 0.5) {
    gbOut(vW);
    if (leaf && uGB.y < 0.5) gl_FragColor.b = 0.4;
    return;
  }
  if (leaf && uMode.w < 0.5) {
    vec3 lV = uCP - vW;
    float ldist = length(lV);
    lV /= ldist;
    float lfocal = uProj.y * u_res.y * 0.5;
    float llod = clamp(log2(max(ldist / lfocal * 480.0, 1e-4)), 0.0, 7.0);
    vec3 la = texture2D(uDA, dmip(vLM, floor(llod + 0.5))).rgb;
    vec3 lalb = la * la;
    vec3 cq = floor(vMP * 1.3 + vSeed * 0.37);
    float h1 = fract(sin(dot(cq, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    float h2 = fract(sin(dot(cq, vec3(39.346, 11.135, 83.155))) * 24634.6345);
    float lg = dot(lalb, vec3(0.3, 0.55, 0.15));
    lalb = mix(vec3(lg), lalb, 0.72);
    lalb *= mix(vec3(1.08, 1.0, 0.62), vec3(0.78, 0.92, 1.05), h1) * (0.7 + 0.5 * h2);
    vec3 LN = normalize(vN);
    vec3 sunL = normalize(uFogSun + vec3(0.0, 0.001, 0.0));
    float wrap = max(dot(LN, sunL) * 0.5 + 0.5, 0.0);
    float back = pow(max(dot(-lV, sunL), 0.0), 3.0);
    vec3 E0 = vIrr.rgb;
    float sunv = smoothstep(0.15, 0.7, dot(E0, vec3(0.3, 0.5, 0.2)) / max(dot(uSunC.rgb, vec3(0.3, 0.5, 0.2)), 0.01) * 1.6);
    vec3 sunT = uSunC.rgb * uSunC.w * (0.05 + 0.1 * wrap) * sunv;
    vec3 LE = E0 * (0.8 + 0.3 * wrap) + uSkyA * (1.3 + 0.9 * (1.0 - sunv)) + E0 * back * 0.6 * sunv + sunT;
    vec3 lcol = lalb * LE + lalb * LE * back * 0.25 * sunv;
    for (int i = 0; i < 24; i++) {
      if (float(i) >= uLtN) break;
      if (uLf[i].x < 0.5) continue;
      vec3 lv = uLt[i].xyz - vW;
      float d2 = dot(lv, lv);
      vec3 L = lv * inversesqrt(d2);
      float pr = lprof(L, uLd[i], uLc[i]);
      if (pr > 0.0) lcol += lalb * uLc[i].rgb * pr / (d2 + 0.05) * (0.5 + 0.5 * abs(dot(LN, L)));
    }
    lcol *= mix(1.0, exp(-ldist * uHaze.x * 0.35), 0.7);
    if (uFog.w > 0.0) {
      float fh = exp(-max(vW.y - uFogS.x, 0.0) * uFogS.y);
      float fa = (1.0 - exp(-ldist * uFog.w * fh)) * uFogS.z;
      float fs = pow(max(dot(-lV, uFogSun), 0.0), 8.0);
      lcol = mix(lcol, uFog.rgb * (1.0 + fs * 0.9), fa);
    }
    gl_FragColor = enc(lcol * uMode.y, 1.0);
    return;
  }
  float mat = floor(vMat + 0.5);
  vec3 Ng = normalize(vN);

  vec3 an = abs(vMN);
  vec2 uv;
  vec3 T;
  vec3 B;
  if (an.x > an.y && an.x > an.z) {
    float s = sign(vMN.x);
    uv = vec2(-s * vMP.z, vMP.y);
    T = vec3(0.0, 0.0, -s);
    B = vec3(0.0, 1.0, 0.0);
  } else if (an.y > an.z) {
    float s = sign(vMN.y);
    uv = vec2(vMP.x, -s * vMP.z);
    T = vec3(1.0, 0.0, 0.0);
    B = vec3(0.0, 0.0, -s);
  } else {
    float s = sign(vMN.z);
    uv = vec2(s * vMP.x, vMP.y);
    T = vec3(s, 0.0, 0.0);
    B = vec3(0.0, 1.0, 0.0);
  }
  vec3 Tw = uMX * T.x + uMY * T.y + uMZ * T.z;
  vec3 Bw = uMX * B.x + uMY * B.y + uMZ * B.z;
  vec3 toC = uCP - vW;
  float dist = length(toC);
  vec3 V = toC / dist;
  float ndv = abs(dot(Ng, V));
  float focal = uProj.y * u_res.y * 0.5;
  float cidA = 0.0;
  float atl = 1.0;
  float tile = 2.0;
  float metal = 0.0;
  float gscale = 1.0;
  vec3 emis = vec3(0.0);
  bool tex = true;
  vec3 alb = vec3(0.8);
  if (mat < 0.5) { cidA = 0.0; gscale = 0.55; }
  else if (mat < 1.5) { cidA = 2.0; metal = 0.35; }
  else if (mat < 2.5) { cidA = 4.0; gscale = 1.6; }
  else if (mat < 3.5) { cidA = 6.0; }
  else if (mat < 4.5) { cidA = 8.0; metal = 0.6; }
  else if (mat < 5.5) { cidA = 10.0; tile = 0.64; metal = 0.3; }
  else if (mat < 6.5) { cidA = 12.0; tile = 1.0; metal = 0.5; }
  else if (mat < 8.5) { cidA = 22.0; tile = 6.0; }
  else if (mat < 9.5) { cidA = 4.0; }
  else if (mat > 19.5 && mat < 20.5) { cidA = 10.0; tile = 1.0; metal = 0.9; }
  else if (mat > 20.5 && mat < 21.5) { cidA = 8.0; tile = 1.0; }
  else if (mat > 21.5 && mat < 22.5) { cidA = 2.0; tile = 1.5; metal = 0.25; }
  else if (mat > 25.5 && mat < 27.5) { cidA = 2.0; tile = 1.5; metal = 0.1; }
  else if (mat > 16.5 && mat < 17.5) { cidA = 12.0; tile = 1.0; metal = 0.55; }
  else if (mat > 17.5 && mat < 18.5) { cidA = 8.0; tile = 1.0; metal = 0.7; }
  else if (mat > 33.5 && mat < 34.5) { cidA = 14.0; metal = 0.45; }
  else if (mat > 34.5 && mat < 35.5) { cidA = 16.0; tile = 1.0; metal = 0.6; }
  else if (mat > 35.5 && mat < 36.5) { cidA = 18.0; tile = 2.0; metal = 0.3; }
  else if (mat > 36.5 && mat < 37.5) { cidA = 20.0; tile = 3.0; }
  else if (mat > 37.5 && mat < 38.5) { cidA = 12.0; tile = 1.0; metal = 0.55; }
  else if ((mat > 38.5 && mat < 39.5) || (mat > 41.5 && mat < 42.5)) { cidA = 22.0; tile = 6.0; }
  else if (mat > 49.5 && mat < 50.5) { atl = 2.0; cidA = 0.0; tile = 3.0; }
  else if (mat > 50.5 && mat < 51.5) { atl = 2.0; cidA = 2.0; tile = 3.0; }
  else if (mat > 51.5 && mat < 52.5) { atl = 2.0; cidA = 4.0; tile = 3.0; }
  else if (mat > 52.5 && mat < 53.5) { atl = 2.0; cidA = 6.0; tile = 3.0; }
  else if (mat > 53.5 && mat < 54.5) { atl = 2.0; cidA = 8.0; tile = 2.0; }
  else if (mat > 54.5 && mat < 55.5) { atl = 2.0; cidA = 10.0; tile = 2.0; }
  else if (mat > 55.5 && mat < 56.5) { atl = 2.0; cidA = 12.0; tile = 2.0; }
  else if (mat > 56.5 && mat < 57.5) { atl = 2.0; cidA = 14.0; tile = 3.0; }
  else if (mat > 57.5 && mat < 58.5) { atl = 2.0; cidA = 16.0; tile = 2.0; }
  else if (mat > 58.5 && mat < 59.5) { atl = 2.0; cidA = 18.0; tile = 2.0; }
  else if (mat > 59.5 && mat < 60.5) { atl = 2.0; cidA = 20.0; tile = 2.0; }
  else if (mat > 60.5 && mat < 61.5) { atl = 2.0; cidA = 22.0; tile = 1.5; }
  else if (mat > 61.5 && mat < 62.5) { atl = 3.0; cidA = 0.0; tile = 4.0; }
  else if (mat > 62.5 && mat < 63.5) { atl = 3.0; cidA = 2.0; tile = 3.0; }
  else if (mat > 63.5 && mat < 64.5) { atl = 3.0; cidA = 4.0; tile = 4.0; }
  else if (mat > 64.5 && mat < 65.5) { atl = 3.0; cidA = 6.0; tile = 3.0; }
  else if (mat > 65.5 && mat < 66.5) { atl = 3.0; cidA = 8.0; tile = 2.0; }
  else if (mat > 66.5 && mat < 67.5) { atl = 3.0; cidA = 10.0; tile = 2.0; }
  else if (mat > 67.5 && mat < 68.5) { atl = 3.0; cidA = 12.0; tile = 2.0; }
  else if (mat > 69.5 && mat < 70.5) { atl = 2.0; cidA = 0.0; tile = 3.0; }
  else if (mat > 70.5 && mat < 71.5) { atl = 1.0; cidA = 22.0; tile = 1.5; }
  else if (mat > 71.5 && mat < 72.5) { atl = 2.0; cidA = 14.0; tile = 3.0; }
  else if (mat > 72.5 && mat < 73.5) { atl = 1.0; cidA = 22.0; tile = 0.5; }
  else if (mat > 73.5 && mat < 74.5) { atl = 1.0; cidA = 10.0; tile = 1.0; metal = 1.0; }
  else { tex = false; }
  bool liquid = (mat > 7.5 && mat < 8.5) || (mat > 38.5 && mat < 39.5) || (mat > 41.5 && mat < 42.5);
  float lod = clamp(log2(max(dist / focal * (""" + f"{S}.0" + """ / tile) / max(sqrt(ndv), 0.3), 1e-4)), 0.0, 6.0);
  vec3 N = Ng;
  float gloss = 0.3;
  if (tex) {
    vec2 tuv = uv / tile + vec2(fract(vSeed * 0.6180339), fract(vSeed * 0.3819660)) * 5.0;
    if (mat > 4.5 && mat < 5.5) tuv = uv / tile + 0.5;
    if (liquid) tuv = uv / tile + vec2(u_timer * 0.013, u_timer * 0.007);
    vec3 a = sampA(atl, cidA, tuv, lod);
    vec3 nm = sampA(atl, cidA + 1.0, tuv, lod);
    if (mat > 69.5 && mat < 70.5) {
      float tl = clamp(log2(max(dist / focal * (1024.0 / 3.0) / 0.75, 1e-4)), 0.0, 6.0);
      float ns = samp(22.0, vW.xz * 0.013, 2.0).r;
      float ns2 = samp(22.0, vW.xz * 0.045 + 0.3, 2.0).g;
      float ns3 = samp(22.0, vW.xz * 0.11 + 0.7, 1.0).b;
      tuv = vW.xz / 3.0;
      uv = vW.xz;
      a = sampA(2.0, 0.0, tuv, tl);
      nm = sampA(2.0, 1.0, tuv, tl);
      float wr = smoothstep(0.84, 0.7, Ng.y + (ns - 0.5) * 0.1);
      float wd = smoothstep(0.7, 0.8, ns2 * 0.75 + ns3 * 0.4) * (1.0 - wr);
      vec3 tsh = texture2D(uTLM, (vW.xz - uTLMP.xy) * uTLMP.zw).rgb;
      float shade = 1.0 - smoothstep(0.32, 0.55, dot(tsh, vec3(0.3, 0.5, 0.2)));
      float wl = smoothstep(0.35, 0.6, ns2 * 0.55 + ns * 0.45 + shade * 0.35 - 0.1) * uTerr.x * shade * (1.0 - wr);
      vec2 tr = uv / 4.0 + 0.37;
      vec3 ar = sampA(2.0, 2.0, tr, tl);
      vec3 nr = sampA(2.0, 3.0, tr, tl);
      vec3 ad = sampA(2.0, 6.0, uv / 2.5, tl);
      vec3 nd = sampA(2.0, 7.0, uv / 2.5, tl);
      float near = 1.0 - smoothstep(6.0, 22.0, dist);
      vec3 dg = sampA(2.0, 0.0, uv * 1.37 + 0.21, max(tl - 1.5, 0.0));
      vec3 gr = mix(a, dg, near * 0.45);
      float gv = ns * 0.6 + ns3 * 0.4;
      gr *= mix(vec3(0.36, 0.5, 0.24), vec3(0.55, 0.6, 0.3), gv) * (0.72 + 0.4 * smoothstep(0.3, 0.7, ns2));
      gr = mix(gr, vec3(dot(gr, vec3(0.45, 0.45, 0.1))) * vec3(1.45, 1.12, 0.58), uTerr.z * (0.75 + 0.25 * gv));
      a = mix(mix(gr, ad * vec3(0.7, 0.66, 0.6), wd), ar * vec3(1.05, 1.0, 0.95), wr);
      if (wl > 0.003) {
        vec2 lu = uv / 1.8 + vec2(ns * 0.3, ns2 * 0.2);
        vec3 la_ = sampA(3.0, 12.0, lu, tl);
        vec3 ln_ = sampA(3.0, 13.0, lu, tl);
        vec3 litter = la_ * (0.85 + 0.3 * ns2) * mix(vec3(1.0), vec3(0.9, 0.95, 0.8), ns3);
        float moss = smoothstep(0.62, 0.78, ns3 * 0.7 + ns * 0.3) * shade;
        litter = mix(litter, gr * vec3(0.62, 0.78, 0.42), moss * 0.7);
        a = mix(a, litter, wl);
        nm = mix(nm, ln_, wl * (1.0 - moss * 0.5));
      }
      nm = mix(mix(nm, nd, wd), nr, wr);
      float pth = texture2D(uTHM, (vW.xz - uTHP.xy) * uTHP.zw).r;
      if (pth > 0.01) {
        vec2 pu = vW.xz / 1.6;
        float pl = max(tl - 0.5, 0.0);
        vec3 pa = sampA(3.0, 6.0, pu, pl);
        vec3 pn = sampA(3.0, 7.0, pu, pl);
        vec3 pd = sampA(2.0, 6.0, vW.xz / 2.2 + 0.3, pl);
        vec3 pdn = sampA(2.0, 7.0, vW.xz / 2.2 + 0.3, pl);
        float gm = smoothstep(0.35, 0.65, ns2 + (ns3 - 0.5) * 0.5);
        float pe = smoothstep(0.2, 0.7, pth + (ns3 - 0.5) * 0.5);
        a = mix(a, mix(pd * vec3(0.86, 0.75, 0.58), pa * vec3(0.76, 0.7, 0.6), gm), pe);
        nm = mix(nm, mix(pdn, pn, gm), pe);
        vec3 pdd = sampA(3.0, 6.0, vW.xz / 0.55 + 0.31, max(pl - 1.0, 0.0));
        float dl_ = dot(pdd, vec3(0.33));
        a *= mix(1.0, clamp(0.45 + dl_ * 1.6, 0.6, 1.5), pe * near * 0.8);
        if (uTerr.x > 0.0) {
          vec3 la2 = sampA(3.0, 12.0, vW.xz / 1.8 + 0.17, pl);
          vec3 ln2 = sampA(3.0, 13.0, vW.xz / 1.8 + 0.17, pl);
          float lit = uTerr.x * clamp((1.0 - smoothstep(0.5, 0.95, pth)) * 0.85 + smoothstep(0.6, 0.85, ns3 * 0.6 + ns2 * 0.4) * 0.5, 0.0, 1.0);
          a = mix(a, la2 * 0.95, lit * pe);
          nm = mix(nm, ln2, lit * pe);
        }
      }
    }
    float sv = fract(vSeed * 0.7548777);
    alb = a * a * (1.0 + (sv - 0.5) * 0.16) * mix(vec3(1.0), vec3(1.04, 1.0, 0.9), step(0.82, fract(vSeed * 0.391)));
    if (mat > 20.5 && mat < 21.5) alb *= 0.45;
    if (mat > 21.5 && mat < 22.5) alb *= 0.6;
    if (mat > 25.5 && mat < 26.5) alb = alb * vec3(2.2, 1.45, 0.25);
    if (mat > 26.5 && mat < 27.5) {
      float st = step(0.5, fract((vW.x + vW.y + vW.z) * 3.0));
      alb = mix(alb * 0.25, alb * vec3(2.2, 1.45, 0.25), st);
    }
    if (mat > 70.5 && mat < 71.5) {
      float lv = fract(vSeed * 0.618);
      float n1 = a.r;
      alb = mix(vec3(0.03, 0.07, 0.015), vec3(0.11, 0.2, 0.04), smoothstep(0.25, 0.75, n1)) * (0.75 + 0.5 * lv);
      alb *= mix(vec3(1.0), vec3(1.25, 1.05, 0.6), step(0.8, lv));
      nm = vec3(0.5 + (a.g - 0.5) * 0.8, 0.5 + (a.b - 0.5) * 0.8, 0.2);
    }
    if (mat > 71.5 && mat < 72.5) alb = mix(alb, vec3(0.5 + 0.4 * fract(vSeed * 0.31), 0.5 + 0.4 * fract(vSeed * 0.53), 0.5 + 0.4 * fract(vSeed * 0.77)) * 0.7, 0.75);
    if (mat > 72.5 && mat < 73.5) {
      vec3 fc = vec3(0.5 + 0.5 * sin(vSeed * 1.7), 0.35 + 0.3 * sin(vSeed * 2.9 + 1.0), 0.3 + 0.3 * sin(vSeed * 4.1 + 2.0));
      alb = fc * (0.25 + 0.15 * a.r);
      nm = vec3(0.5, 0.5, 0.15);
    }
    if (mat > 73.5 && mat < 74.5) alb = vec3(1.0, 0.72, 0.28) * (0.75 + 0.25 * a.r);
    vec2 nxy = nm.xy * 2.0 - 1.0;
    float nz = sqrt(max(1.0 - dot(nxy, nxy), 0.0));
    gloss = nm.z;
    N = normalize(Tw * nxy.x + Bw * nxy.y + Ng * nz);
    if (mat > 4.5 && mat < 5.5) {
      vec2 f = fract(tuv) - 0.5;
      float r = length(f);
      float ring = smoothstep(0.035, 0.0, abs(r - 0.2));
      emis = uEmit * ring * 2.5;
    }
    if (liquid) {
      vec2 q = uv * 0.35;
      float n1 = samp(22.0, q * 0.5 + vec2(u_timer * 0.02, -u_timer * 0.015), 2.0).r;
      float n2 = samp(22.0, q * 1.3 + vec2(-u_timer * 0.035, u_timer * 0.02), 2.0).g;
      float f = smoothstep(0.35, 0.75, n1 * 0.6 + n2 * 0.5);
      if (mat > 38.5 && mat < 39.5) {
        alb = mix(vec3(0.004, 0.02, 0.035), vec3(0.02, 0.09, 0.13), f);
        emis = mix(vec3(0.0, 0.004, 0.008), vec3(0.03, 0.14, 0.2), f * f);
        metal = 0.0;
      } else if (mat > 41.5) {
        alb = mix(vec3(0.12, 0.012, 0.0), vec3(0.4, 0.08, 0.0), f);
        emis = mix(vec3(0.5, 0.05, 0.0), vec3(3.2, 1.0, 0.12), f * f);
      } else {
        alb = mix(vec3(0.05, 0.22, 0.02), vec3(0.25, 0.75, 0.05), f);
        emis = mix(vec3(0.06, 0.35, 0.02), vec3(0.55, 1.6, 0.15), f * f);
      }
      vec2 g = vec2(n1 - 0.5, n2 - 0.5) * 0.6;
      N = normalize(Ng + Tw * g.x + Bw * g.y);
      gloss = 0.95;
    }
    if (mat > 5.5 && mat < 6.5) {
      float st = step(0.5, fract((vW.x + vW.z) * 1.25));
      alb = mix(alb * 0.1, alb * vec3(1.9, 1.3, 0.18), st);
      gloss = 0.35;
    }
    if (mat > 16.5 && mat < 17.5) {
      vec2 cu = uv * 1.0;
      vec2 cf = fract(cu) - 0.5;
      float edge = smoothstep(0.43, 0.48, max(abs(cf.x), abs(cf.y)));
      float ch = fract(cu.y * 2.0 - abs(cf.x) * 1.4 - u_timer * 0.9);
      float band = smoothstep(0.0, 0.06, ch) * smoothstep(0.3, 0.18, ch) * step(abs(cf.x), 0.3);
      alb = alb * 0.22 * vec3(0.95, 0.97, 1.05);
      alb = mix(alb, vec3(0.9, 0.42, 0.06), band * 0.6);
      emis = vec3(1.0, 0.48, 0.1) * (band * 1.7 + edge * 1.1 + 0.05);
      gloss = max(gloss, 0.55);
    }
    if (mat > 17.5 && mat < 18.5) {
      vec2 g = fract(uv * vec2(7.0, 1.4));
      float slot = smoothstep(0.3, 0.38, g.x) * smoothstep(0.92, 0.84, g.x) * smoothstep(0.03, 0.1, g.y) * smoothstep(0.97, 0.9, g.y);
      alb = mix(alb * 0.3, vec3(0.005), slot);
      float fl = 0.75 + 0.25 * sin(u_timer * 9.0 + uv.x * 3.0) * sin(u_timer * 5.3 + uv.y * 2.0);
      emis = vec3(0.35, 0.65, 1.0) * slot * 0.55 * fl;
      N = normalize(mix(N, Ng, slot));
    }
    if (mat > 8.5 && mat < 9.5) {
      float chev = fract((abs(uv.x - floor(uv.x + 0.5)) * 0.8 + uv.y) * 1.0 - u_timer * 0.6);
      float band = smoothstep(0.0, 0.08, chev) * smoothstep(0.45, 0.3, chev);
      alb = alb * vec3(1.0, 0.85, 0.6);
      emis = vec3(1.0, 0.62, 0.2) * (0.35 + band * 1.6);
    }
  } else {
    if (mat < 10.5) {
      vec2 g = abs(fract(uv * 4.0) - 0.5);
      float grid = smoothstep(0.46, 0.5, max(g.x, g.y));
      emis = vec3(4.4, 4.3, 4.1) * (1.0 - grid * 0.45);
      alb = vec3(0.0);
    } else if (mat < 11.5) {
      alb = vec3(0.04, 0.045, 0.05);
      gloss = 0.7;
    } else if (mat < 12.5) {
      alb = vec3(0.04);
      emis = uEmit;
    } else if (mat < 13.5) {
      alb = vec3(0.78, 0.8, 0.83);
      gloss = 0.55;
    } else if (mat < 14.5) {
      alb = vec3(0.02);
      emis = uEmit * 0.8;
      gloss = 0.9;
    } else if (mat < 15.5) {
      alb = vec3(0.12, 0.13, 0.15);
      gloss = 0.6;
      metal = 0.6;
    } else if (mat < 16.5) {
      alb = vec3(0.86, 0.87, 0.9);
      gloss = 0.7;
    } else if (mat > 76.5 && mat < 77.5) {
      alb = vec3(0.02, 0.025, 0.03);
      gloss = 0.98;
      metal = 0.9;
    } else if (mat > 75.5 && mat < 76.5) {
      vec3 rd = -V;
      float hy = clamp(rd.y * 1.6 + 0.15, 0.0, 1.0);
      emis = mix(vec3(1.5, 1.45, 1.35), vec3(0.45, 0.68, 1.15), hy) * 1.1;
      emis += vec3(0.3, 0.26, 0.2) * smoothstep(0.1, -0.2, rd.y);
      alb = vec3(0.0);
      gloss = 0.97;
    } else if (mat > 74.5 && mat < 75.5) {
      float fl = 0.7 + 0.3 * sin(u_timer * 13.0 + vSeed) * sin(u_timer * 7.3 + vMP.y * 9.0);
      alb = vec3(0.0);
      emis = mix(vec3(2.6, 0.7, 0.08), vec3(3.4, 2.6, 0.9), clamp(1.0 - vMP.y * 3.0, 0.0, 1.0)) * fl;
    } else if (mat > 22.5 && mat < 23.5) {
      alb = vec3(0.045, 0.047, 0.052);
      gloss = 0.45;
    } else if (mat > 23.5 && mat < 24.5) {
      alb = vec3(0.72, 0.4, 0.05);
      gloss = 0.5;
    } else if (mat > 27.5 && mat < 28.5) {
      alb = vec3(0.02);
      emis = vec3(3.4, 3.25, 3.0);
    } else if (mat > 28.5 && mat < 29.5) {
      alb = vec3(0.02);
      emis = vec3(3.2, 1.7, 0.45);
    } else if (mat > 30.5 && mat < 31.5) {
      alb = vec3(0.02);
      emis = vec3(2.6, 0.18, 0.12) * (0.75 + 0.25 * sin(u_timer * 3.0 + vSeed));
    } else if (mat > 32.5 && mat < 33.5) {
      alb = vec3(0.02);
      emis = vec3(0.25, 1.9, 0.55) * (0.8 + 0.2 * step(0.5, fract(u_timer * 0.7 + vSeed * 0.13)));
    } else if (mat > 18.5 && mat < 19.5) {
      float Hh = 4.6;
      float Ww = max(vSeed, 1.0) / 32.0 * Hh;
      float Dd = 7.0;
      vec3 vd = -V;
      vec3 ld = vec3(dot(vd, Tw), dot(vd, Bw), -dot(vd, Ng)) + vec3(1e-4);
      vec3 lp = vec3(vLM.x * Ww, vLM.y * Hh, 0.0);
      vec3 corner = vW - Tw * lp.x - Bw * lp.y;
      float wh = hash12(floor(corner.xz * 0.37) + floor(corner.y * 0.23) * 7.1);
      vec3 b0 = vec3(-2.0, -1.2, 0.0);
      vec3 b1 = vec3(Ww + 2.0, Hh + 1.6, Dd);
      vec3 tf = max((b0 - lp) / ld, (b1 - lp) / ld);
      float th = min(min(tf.x, tf.y), tf.z);
      vec3 h = lp + ld * th;
      vec3 key = mix(vec3(1.35, 1.12, 0.82), vec3(0.85, 0.95, 1.15), step(0.62, wh));
      float top = smoothstep(b0.y, b1.y, h.y);
      vec3 ic;
      vec2 pg = abs(fract(vec2(h.x, h.y) / 1.2) - 0.5);
      float seam = smoothstep(0.47, 0.5, max(pg.x, pg.y));
      if (tf.z <= th + 1e-3) {
        ic = key * (0.35 + 0.45 * top) * (1.0 - seam * 0.5);
        float fx = Ww * (0.5 + 0.38 * sin(u_timer * (0.32 + wh * 0.2) + wh * 40.0));
        if (wh < 0.4) {
          vec2 q = vec2(h.x - fx, h.y - (b0.y + 0.85));
          float body = step(abs(q.x), 0.22) * step(0.0, q.y) * step(q.y, 0.95);
          float head = step(length(q - vec2(0.0, 1.13)), 0.14);
          ic *= 1.0 - 0.9 * max(body, head);
        } else if (wh < 0.75) {
          float px = Ww * (0.5 + 0.42 * sin(u_timer * 0.45 + wh * 23.0));
          vec2 q = vec2(h.x - px, h.y - (b0.y + 0.6));
          float plat = step(abs(q.x), 0.9) * step(abs(q.y), 0.12);
          ic = mix(ic, vec3(0.08, 0.085, 0.09), plat);
          ic += vec3(0.9, 0.5, 0.1) * plat * step(abs(q.y - 0.12), 0.03) * 2.0;
        }
      } else if (tf.y <= th + 1e-3) {
        if (ld.y > 0.0) {
          float st = step(abs(fract(h.z / 1.6 + 0.25) - 0.5), 0.08) * step(abs(h.x - Ww * 0.5), Ww * 0.42);
          ic = key * 0.12 + vec3(2.2, 2.0, 1.7) * st;
        } else {
          ic = key * (0.18 + 0.25 * smoothstep(0.0, Dd, h.z));
        }
      } else {
        ic = key * (0.22 + 0.3 * top) * (1.0 - seam * 0.4);
      }
      if (wh > 0.5) {
        float ang = u_timer * 2.6 + wh * 17.0;
        vec3 bc = vec3(Ww * 0.5, Hh + 1.2, Dd - 0.4);
        vec3 dv = normalize(h - bc);
        float sweep = pow(max(dot(normalize(vec2(dv.x, dv.z)), vec2(sin(ang), cos(ang))), 0.0), 18.0);
        ic += vec3(1.6, 0.55, 0.08) * sweep * (0.6 + 0.4 * (1.0 - dv.y));
        ic += vec3(2.5, 0.9, 0.15) * step(length(h - bc), 0.25);
      }
      emis = ic * exp(-h.z * 0.05);
      alb = vec3(0.0);
      gloss = 0.98;
    } else if (mat > 24.5 && mat < 25.5) {
      float Hh = 1.8;
      float Ww = max(vSeed, 1.0) / 32.0 * Hh;
      float Dd = 3.4;
      vec3 vd = -V;
      vec3 ld = vec3(dot(vd, Tw), dot(vd, Bw), -dot(vd, Ng));
      ld += vec3(1e-4);
      vec3 lp = vec3(vLM.x * Ww, vLM.y * Hh, 0.0);
      vec3 b0 = vec3(-1.4, -0.75, 0.0);
      vec3 b1 = vec3(Ww + 1.4, Hh + 0.95, Dd);
      vec3 tf = max((b0 - lp) / ld, (b1 - lp) / ld);
      float th = min(min(tf.x, tf.y), tf.z);
      vec3 h = lp + ld * th;
      vec3 ic = vec3(0.03, 0.034, 0.042);
      float glow = 0.0;
      if (tf.z <= th + 1e-3) {
        for (int k = 0; k < 3; k++) {
          float cx = Ww * (0.2 + 0.3 * float(k));
          vec2 dm = abs(h.xy - vec2(cx, 0.85)) - vec2(0.32, 0.2);
          float m = step(max(dm.x, dm.y), 0.0);
          float scan = 0.85 + 0.15 * sin(h.y * 90.0 + u_timer * 4.0 + float(k) * 2.0);
          ic += m * vec3(0.18, 0.5, 0.85) * 1.7 * scan;
          glow += exp(-max(max(dm.x, dm.y), 0.0) * 6.0) * 0.12;
        }
        ic += vec3(0.1, 0.25, 0.4) * glow;
      } else if (tf.y <= th + 1e-3) {
        if (ld.y > 0.0) {
          float st = step(abs(fract(h.z / 1.4 + 0.25) - 0.5), 0.07) * step(abs(h.x - Ww * 0.5), Ww * 0.45);
          ic = vec3(0.025) + vec3(1.5, 1.35, 1.1) * st;
        } else {
          ic = vec3(0.02, 0.022, 0.026) + vec3(0.04, 0.08, 0.13) * smoothstep(1.0, 3.4, h.z);
        }
      } else {
        ic = vec3(0.028, 0.03, 0.036) + vec3(0.03, 0.06, 0.1) * smoothstep(1.5, 3.4, h.z);
      }
      if (ld.y < 0.0) {
        float td = (0.75 - lp.y) / ld.y;
        vec3 hd = lp + ld * td;
        if (td > 0.0 && td < th && hd.z > Dd - 1.1) {
          ic = vec3(0.03, 0.032, 0.036) + vec3(0.12, 0.3, 0.5) * 0.35 * smoothstep(Dd - 1.1, Dd, hd.z);
        }
      }
      ic *= exp(-h.z * 0.12);
      emis = ic * 0.8;
      alb = vec3(0.0);
      gloss = 0.98;
    }
  }
  float prough = -1.0;
  if (((vIrr.w > 0.5 && vIrr.w < 2.5) || leaf) && uMode.w < 0.5) {
    float lodd = clamp(log2(max(dist / focal * 1000.0 / max(sqrt(ndv), 0.3), 1e-4)), 0.0, 7.0);
    vec3 da = dsamp(uDA, vLM, lodd);
    vec3 dn = dsamp(uDN, vLM, max(lodd - 1.0, 0.0)) * 2.0 - 1.0;
    vec3 dr = dsamp(uDR, vLM, max(lodd - 1.0, 0.0));
    alb = da * da;
    vec3 T = normalize(vTan - Ng * dot(vTan, Ng));
    vec3 Bt = cross(Ng, T) * (vIrr.w > 1.5 ? -1.0 : 1.0);
    N = normalize(T * dn.x + Bt * dn.y + Ng * max(dn.z, 0.05));
    metal = dr.g;
    prough = max(dr.r, 0.12 + lodd * 0.07);
    emis = leaf ? vec3(0.0) : alb / max(max(alb.r, max(alb.g, alb.b)), 0.02) * max(dr.b - 0.04, 0.0) * 3.4;
    if (leaf) {
      N = Ng;
      metal = 0.0;
      prough = max(prough, 0.7);
      vec3 cq = floor(vMP * 1.3 + vSeed * 0.37);
      float h1 = fract(sin(dot(cq, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
      float h2 = fract(sin(dot(cq, vec3(39.346, 11.135, 83.155))) * 24634.6345);
      float lg = dot(alb, vec3(0.3, 0.55, 0.15));
      alb = mix(vec3(lg), alb, 0.72);
      alb *= mix(vec3(1.08, 1.0, 0.62), vec3(0.78, 0.92, 1.05), h1) * (0.7 + 0.5 * h2);
    }
  }
  if (uMode.w > 0.5) {
    float lodp = clamp(log2(max(dist / focal * uPR.w / max(sqrt(ndv), 0.3), 1e-4)), 0.0, 6.0);
    vec3 pa = sampP(0.0, vLM, lodp);
    vec3 pn = sampP(1.0, vLM, lodp) * 2.0 - 1.0;
    float sb = sin(vBA);
    float cb = cos(vBA);
    pn = vec3(pn.x, pn.y * cb - pn.z * sb, pn.y * sb + pn.z * cb);
    vec3 pc = sampP(2.0, vLM, lodp);
    alb = pa * pa;
    N = normalize(uMX * pn.x + uMY * pn.y + uMZ * pn.z);
    if (dot(N, Ng) < -0.2) N = Ng;
    metal = pc.g;
    prough = pc.r;
    emis = uEmit * smoothstep(0.18, 0.55, pc.b) * pc.b * 1.6;
  }
  vec3 E;
  float so = 1.0;
  if (uMode.x < 0.5 && vIrr.w > 3.5 && vIrr.w < 4.5) {
    vec3 tl = texture2D(uTLM, (vW.xz - uTLMP.xy) * uTLMP.zw).rgb;
    E = tl * tl * 4.0;
    so = clamp(dot(E, vec3(0.4)) * 1.4 - 0.1, 0.0, 1.0);
    if (uTerr.y > 0.0) {
      float tlum = dot(tl, vec3(0.3, 0.5, 0.2));
      float dm = smoothstep(0.18, 0.42, tlum) * (1.0 - smoothstep(0.5, 0.75, tlum));
      vec2 wq = vW.xz * 0.9 - uWind2.xy * u_timer * 0.6;
      float wn = vnoise(wq) * 0.6 + vnoise(wq * 2.3 + 7.1 + u_timer * 0.35) * 0.4;
      E *= 1.0 + dm * uTerr.y * (smoothstep(0.35, 0.75, wn) * 1.4 - 0.5);
    }
  } else if (uMode.x < 0.5 && vIrr.w > 0.5) {
    E = vIrr.rgb;
    so = clamp(dot(E, vec3(0.4)) * 1.4 - 0.1, 0.0, 1.0);
  } else if (uMode.x < 0.5) {
    vec3 ls = texture2D(uLM, vec2(vLM.x, vLM.y / 3.0)).rgb;
    vec2 dgr = texture2D(uLM, vec2(vLM.x, vLM.y / 3.0 + 2.0 / 3.0)).rg;
    float hf = samp(22.0, vec2(uv.x * 2.6, uv.y * 0.11 + vSeed * 0.013), 1.0).r;
    float hf2 = samp(22.0, uv * 1.7, 1.0).g;
    float dm = clamp(dgr.x * (0.3 + 1.4 * hf) * (0.75 + 0.5 * hf2), 0.0, 1.0);
    float rm = clamp(dgr.y * (0.2 + 1.6 * hf), 0.0, 1.0);
    alb *= mix(vec3(1.0), vec3(0.5, 0.48, 0.45), dm * 0.9);
    alb = mix(alb, alb * vec3(0.72, 0.45, 0.26) + vec3(0.03, 0.012, 0.0), rm);
    gloss *= 1.0 - dm * 0.7;
    E = ls * ls * 4.0;
    vec3 dv = texture2D(uLM, vec2(vLM.x, vLM.y / 3.0 + 1.0 / 3.0)).rgb * 2.0 - 1.0;
    float dl = length(dv);
    vec3 dn = dv / max(dl, 1e-4);
    float ng = max(dot(Ng, dn), 0.12);
    float nl = max(dot(N, dn), 0.0);
    E *= clamp(mix(1.0, nl / ng, clamp(dl * 1.1, 0.0, 0.9)), 0.0, 2.0);
    so = clamp(dot(E, vec3(0.4)) * 1.4 - 0.1, 0.0, 1.0);
  } else {
    vec3 n2 = N * N;
    E = n2.x * (N.x > 0.0 ? uA0 : uA1) + n2.y * (N.y > 0.0 ? uA2 : uA3) + n2.z * (N.z > 0.0 ? uA4 : uA5);
  }
  float o = occ(vW, N, uO1) + occ(vW, N, uO2);
  for (int i = 0; i < 4; i++) {
    if (float(i) >= uShN || uMode.x > 0.5 || leaf) break;
    vec3 ax = uSX[i].xyz;
    vec3 ay = uSY[i].xyz;
    vec3 az = cross(ax, ay);
    vec3 r0 = vW - uSC[i].xyz;
    vec3 lp = vec3(dot(r0, ax), dot(r0, ay), dot(r0, az));
    vec3 hs = vec3(uSX[i].w, uSY[i].w, uSC[i].w);
    vec3 q = abs(lp) - hs;
    float bd = length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
    float rr = min(min(hs.x, hs.y), hs.z) * 0.5 + 0.05;
    vec3 tc = normalize(-r0);
    o += 0.85 * exp(-max(bd, 0.0) / rr) * (0.35 + 0.65 * max(dot(N, tc), 0.0)) * step(0.004, bd);
  }
  float px = dist / focal;
  float ao = (1.0 - clamp(o, 0.0, 0.85)) * mix(vAO, 0.8 + vAO * 0.2, clamp(px / 0.012 - 0.6, 0.0, 1.0));
  vec3 F0 = mix(vec3(0.04), alb, metal);
  vec3 diff = alb * (1.0 - metal * 0.85);
  float rough = mix(0.85, 0.12, clamp(gloss * gscale, 0.0, 1.0));
  if (prough >= 0.0) rough = clamp(prough, 0.08, 1.0);
  float a = rough * rough;
  vec3 spec = vec3(0.0);
  vec3 ddir = vec3(0.0);
  vec3 dloss = vec3(0.0);
  float jit = hash12(gl_FragCoord.xy + fract(u_timer * 13.7) * 97.0);
  float jit2 = hash12(gl_FragCoord.yx * 1.37 + fract(u_timer * 7.31) * 53.0);
  bool props = uMode.x > 0.5;
  for (int i = 0; i < 24; i++) {
    if (float(i) >= uLtN) break;
    if (leaf && uLf[i].x < 0.5) continue;
    vec4 L4 = uLt[i];
    vec4 D4 = uLd[i];
    vec4 C4 = uLc[i];
    vec3 lv = L4.xyz - vW;
    float d2 = dot(lv, lv);
    vec3 L = lv * inversesqrt(d2);
    float pr = lprof(L, D4, C4);
    if (pr <= 0.0) continue;
    vec3 Ei = C4.rgb * pr / (d2 + 0.05);
    float vis = 1.0;
    if (uMode.z < 0.5 && !leaf) {
      float lr = max(L4.w, 0.18);
      vec3 j1 = (vec3(jit, jit2, fract(jit + jit2 * 1.7)) - 0.5) * 2.0 * lr;
      vec3 j2 = (vec3(fract(jit + 0.5), fract(jit2 + 0.37), fract(jit * 3.1 + 0.2)) - 0.5) * 2.0 * lr;
      vec3 po = vW + Ng * 0.03;
      vis = 0.5 * (dynVis(po, L4.xyz + j1 - D4.xyz * 0.02) + dynVis(po, L4.xyz + j2 - D4.xyz * 0.02));
    }
    float ap = clamp(a + L4.w * inversesqrt(d2) * 0.5, 0.0, 1.0);
    vec3 H = normalize(L + V);
    float nh = max(dot(N, H), 0.0);
    float nl = max(dot(N, L), 0.0);
    float den = nh * nh * (ap * ap - 1.0) + 1.0;
    float D = ap * ap / (3.14159 * den * den) * (a / ap);
    float vh = max(dot(V, H), 0.0);
    vec3 F = F0 + (1.0 - F0) * pow(1.0 - vh, 5.0);
    spec += F * (D * nl * 0.9) * Ei * vis;
    if (props || uLf[i].x > 0.5) ddir += Ei * nl * vis;
    else dloss += Ei * max(dot(Ng, L), 0.0) * (1.0 - vis);
  }
  vec3 envs = vec3(0.0);
  if (uEnvP.w > 0.5 && !leaf) {
    vec3 R = reflect(-V, N);
    vec3 pr = vW;
    if (all(greaterThan(pr, uBox0)) && all(lessThan(pr, uBox1))) {
      vec3 Rs = R + vec3(1e-5);
      vec3 tm = max((uBox1 - pr) / Rs, (uBox0 - pr) / Rs);
      float t = min(min(tm.x, tm.y), tm.z);
      R = mix(R, pr + R * t - uEnvP.xyz, 0.85);
    }
    vec3 ev = envSample(R, rough);
    if (uSSR.x > 0.5 && rough < 0.55) {
      vec4 sr = ssr(vW + Ng * 0.01, reflect(-V, N));
      ev = mix(ev, sr.rgb, sr.a * (1.0 - smoothstep(0.3, 0.55, rough)));
    }
    envs = ev * envBRDF(F0, rough, max(dot(N, V), 0.02)) * uEnvP.w;
    envs *= mix(1.0, so, 0.7);
  }
  if (leaf) {
    vec3 sunL = normalize(uFogSun + vec3(0.0, 0.001, 0.0));
    float wrap = max(dot(N, sunL) * 0.5 + 0.5, 0.0);
    float back = pow(max(dot(-V, sunL), 0.0), 3.0);
    vec3 skyA = uSkyA;
    vec3 sunT = uSunC.rgb * uSunC.w * (0.05 + 0.1 * wrap);
    E = E * (0.8 + 0.3 * wrap) + skyA * 1.3 + E * back * 0.6 + sunT;
    emis += alb * E * back * 0.25;
    ao = mix(ao, 1.0, 0.6);
    spec *= 0.12;
    envs = vec3(0.0);
  }
  vec3 col = diff * (max(E - dloss, 0.0) * ao + ddir) + spec * mix(1.0, so, props ? 0.0 : 1.0) * ao + envs * ao + emis;
  col += uRim * (0.1 + 1.3 * pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.4));
  float ext = exp(-dist * uHaze.x * 0.35);
  col = col * mix(1.0, ext, 0.7);
  if (uFog.w > 0.0) {
    float fh = exp(-max(vW.y - uFogS.x, 0.0) * uFogS.y);
    float fa = (1.0 - exp(-dist * uFog.w * fh)) * uFogS.z;
    float fs = pow(max(dot(-V, uFogSun), 0.0), 8.0);
    col = mix(col, uFog.rgb * (1.0 + fs * 0.9), fa);
  }
  if (uSSR.x < 0.5) col += haze(uCP, -V, dist, jit);
  gl_FragColor = enc(col * uMode.y, 1.0);
}
"""

PART_VS = HEAD + CAM_U + PROJECT + """
attribute vec4 aSeed;
attribute vec2 aCorner;
uniform float u_timer;
uniform vec4 uPM;
uniform vec3 uQC;
uniform vec3 uQR;
uniform vec3 uQU;
uniform vec3 uQN;
uniform vec4 uLt[24];
uniform float uLtN;
uniform vec4 uLd[24];
uniform vec4 uLc[24];
varying vec2 vC;
varying float vA;
varying vec3 vW;
void main() {
  vec3 p;
  float sz;
  float a;
  if (uPM.x > 1.5 && uPM.x < 2.5) {
    float f = pow(aSeed.x, 0.55);
    p = mix(uQR, uQC, f) + (aSeed.yzw - 0.5) * 0.05 * (1.0 - f);
    sz = 0.01 + 0.05 * f * f * f;
    a = (0.25 + f * f * 1.8) * uPM.z;
  } else if (uPM.x > 2.5) {
    float t = uPM.y;
    vec3 dir = normalize(uQN * 1.2 + (aSeed.xyz - 0.5) * 2.2);
    float sp = 2.0 + aSeed.w * 5.0;
    p = uQC + dir * sp * t + vec3(0.0, -7.0, 0.0) * t * t;
    a = pow(max(1.0 - t / 0.6, 0.0), 2.0) * 1.6 * uPM.z;
    sz = 0.006 + aSeed.w * 0.008;
    if (aSeed.w > 0.94) {
      p = uQC + uQN * 0.05;
      sz = 0.35 * (1.0 + t * 3.0);
      a = max(1.0 - t / 0.18, 0.0) * 2.0 * uPM.z;
    }
  } else if (uPM.x > 3.5) {
    float life = fract(u_timer * (0.45 + aSeed.w * 0.5) + aSeed.z);
    float sw = u_timer * (1.5 + aSeed.w) + aSeed.x * 6.28;
    p = uQC + vec3((aSeed.x - 0.5) * 2.0 * uQR.x + sin(sw) * 0.12, life * uPM.y, (aSeed.y - 0.5) * 2.0 * uQR.z + cos(sw) * 0.12);
    a = smoothstep(0.0, 0.08, life) * (1.0 - life) * 0.9 * uPM.z;
    sz = 0.006 + aSeed.w * 0.012;
  } else if (uPM.x < 0.5) {
    vec3 cell = vec3(14.0, 9.0, 14.0);
    vec3 drift = vec3(sin(u_timer * 0.11 + aSeed.w * 6.28), -0.06 - aSeed.w * 0.05, cos(u_timer * 0.13 + aSeed.z * 6.28)) * u_timer * 0.12;
    p = uCP + (fract(aSeed.xyz + drift / cell - uCP / cell) - 0.5) * cell;
    p.y = clamp(p.y, uPM.y, uPM.z);
    float lit = 0.0;
    for (int i = 0; i < 24; i++) {
      if (float(i) >= uLtN) break;
      vec3 lv = uLt[i].xyz - p;
      float d2 = dot(lv, lv);
      vec3 l = lv * inversesqrt(d2);
      float c = dot(-l, uLd[i].xyz);
      float pr = uLc[i].w < -1.5 ? max(c, 0.0) : smoothstep(uLd[i].w, uLc[i].w, c);
      lit += dot(uLc[i].rgb, vec3(0.33)) * pr / (d2 + 0.5) * 0.12;
    }
    a = (0.06 + lit * 0.9) * (0.5 + 0.5 * sin(u_timer * (1.0 + aSeed.x * 2.0) + aSeed.y * 30.0));
    sz = 0.008 + aSeed.w * 0.012;
  } else {
    float life = fract(u_timer * (0.35 + aSeed.w * 0.4) + aSeed.z);
    float ang = aSeed.x * 6.28318 + u_timer * 0.4;
    float rr = 1.0 + life * (0.25 + aSeed.y * 0.5);
    p = uQC + uQR * (cos(ang) * uPM.y * rr) + uQU * (sin(ang) * uPM.z * rr) + uQN * (0.02 + life * (0.1 + aSeed.y * 0.35));
    a = (1.0 - life) * smoothstep(0.0, 0.1, life) * uPM.w;
    sz = 0.006 + aSeed.w * 0.01;
  }
  vec3 r = p - uCP;
  float d = max(dot(r, uCF), 0.05);
  sz = max(sz, d * 0.0025);
  vec3 w = p + (uCR * aCorner.x + uCU * aCorner.y) * sz;
  vC = aCorner;
  vA = a;
  vW = w;
  gl_Position = project(w);
}
"""

PART_FS = HEAD + """
uniform float u_timer;
uniform vec3 uCol;
""" + GATE + ENC + """
varying vec2 vC;
varying float vA;
varying vec3 vW;
void main() {
  gate(vW);
  float r = dot(vC, vC);
  float g = exp(-r * 3.5) * vA;
  if (g < 0.003) discard;
  gl_FragColor = vec4(sqrt(clamp(uCol * g * 0.25, 0.0, 1.0)), 0.0);
}
"""

QUAD_VS = HEAD + """
attribute vec3 aPos;
void main() {
  gl_Position = vec4(aPos.xy, 0.0, 1.0);
}
"""

BRIGHT_FS = HEAD + """
uniform sampler2D uSrc;
uniform vec2 uTx;
uniform vec4 uBP;
uniform vec2 u_res;
vec3 dec(vec3 e) { return e * e * 4.0; }
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 c = dec(texture2D(uSrc, uv + uTx * vec2(-1.0, -1.0)).rgb);
  c += dec(texture2D(uSrc, uv + uTx * vec2(1.0, -1.0)).rgb);
  c += dec(texture2D(uSrc, uv + uTx * vec2(-1.0, 1.0)).rgb);
  c += dec(texture2D(uSrc, uv + uTx * vec2(1.0, 1.0)).rgb);
  c *= 0.25;
  float l = max(max(c.r, c.g), c.b);
  float k = max(l - uBP.x, 0.0) / max(l, 1e-4);
  c *= k * uBP.y;
  gl_FragColor = vec4(sqrt(clamp(c * 0.25, 0.0, 1.0)), 1.0);
}
"""

BLUR_FS = HEAD + """
uniform sampler2D uSrc;
uniform vec2 uDir;
uniform vec2 u_res;
vec3 dec(vec3 e) { return e * e * 4.0; }
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 c = dec(texture2D(uSrc, uv).rgb) * 0.227027;
  c += dec(texture2D(uSrc, uv + uDir * 1.3846).rgb) * 0.316216;
  c += dec(texture2D(uSrc, uv - uDir * 1.3846).rgb) * 0.316216;
  c += dec(texture2D(uSrc, uv + uDir * 3.2308).rgb) * 0.070270;
  c += dec(texture2D(uSrc, uv - uDir * 3.2308).rgb) * 0.070270;
  gl_FragColor = vec4(sqrt(clamp(c * 0.25, 0.0, 1.0)), 1.0);
}
"""

COMP_FS = HEAD + """
uniform sampler2D uScene;
uniform sampler2D uB1;
uniform sampler2D uB2;
uniform vec2 uTx;
uniform vec4 uPost;
uniform vec4 uFx;
uniform vec3 uFlash;
uniform vec4 uGrade;
uniform sampler2D uLum;
uniform vec4 uAE;
uniform vec2 u_res;
uniform float u_timer;
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
vec3 S(vec2 p) { return texture2D(uScene, p).rgb; }
vec3 fxaa(vec2 uv) {
  vec3 nw = S(uv + vec2(-1.0, -1.0) * uTx);
  vec3 ne = S(uv + vec2(1.0, -1.0) * uTx);
  vec3 sw = S(uv + vec2(-1.0, 1.0) * uTx);
  vec3 se = S(uv + vec2(1.0, 1.0) * uTx);
  vec3 m = S(uv);
  float lnw = luma(nw);
  float lne = luma(ne);
  float lsw = luma(sw);
  float lse = luma(se);
  float lm = luma(m);
  float lmin = min(lm, min(min(lnw, lne), min(lsw, lse)));
  float lmax = max(lm, max(max(lnw, lne), max(lsw, lse)));
  if (lmax - lmin < max(0.04, lmax * 0.1)) return m;
  vec2 dir = vec2(-((lnw + lne) - (lsw + lse)), (lnw + lsw) - (lne + lse));
  float red = max((lnw + lne + lsw + lse) * 0.03125, 1.0 / 128.0);
  float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + red);
  dir = clamp(dir * rcp, -8.0, 8.0) * uTx;
  vec3 a = 0.5 * (S(uv + dir * (1.0 / 3.0 - 0.5)) + S(uv + dir * (2.0 / 3.0 - 0.5)));
  vec3 b = a * 0.5 + 0.25 * (S(uv - dir * 0.5) + S(uv + dir * 0.5));
  float lb = luma(b);
  if (lb < lmin || lb > lmax) return a;
  return b;
}
vec3 aces(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 cc = uv - 0.5;
  vec3 e = S(uv) * 1.88 - (S(uv + vec2(uTx.x, 0.0)) + S(uv - vec2(uTx.x, 0.0)) + S(uv + vec2(0.0, uTx.y)) + S(uv - vec2(0.0, uTx.y))) * 0.22;
  e = max(e, 0.0);
  vec2 ca = cc * uFx.z * 0.006;
  e.r = mix(e.r, S(uv + ca).r, 0.85);
  e.b = mix(e.b, S(uv - ca).b, 0.85);
  vec3 c = e * e * 4.0;
  vec3 b1 = texture2D(uB1, uv).rgb;
  vec3 b2 = texture2D(uB2, uv).rgb;
  c += (b1 * b1 * 4.0) * uPost.y + (b2 * b2 * 4.0) * uPost.z;
  float lv = texture2D(uLum, vec2(0.5)).r;
  float lum = lv * lv * 8.0;
  float ae = clamp(pow(uAE.y / max(lum, 0.01), uAE.x), uAE.z, uAE.w);
  c *= uPost.x * uGrade.rgb * ae;
  float lg = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = max(mix(vec3(lg), c, uGrade.w), 0.0);
  c = aces(c);
  float vig = 1.0 - dot(cc, cc) * uPost.w;
  c *= vig;
  c = pow(c, vec3(1.0 / 2.2));
  float lu = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = max(mix(vec3(lu), c, 1.1), 0.0);
  c = mix(c, c * c * (3.0 - 2.0 * c), 0.22);
  c += vec3(-0.006, 0.003, 0.014) * (1.0 - lu) * (1.0 - lu) + vec3(0.006, 0.003, -0.004) * lu * lu;
  c += (hash12(gl_FragCoord.xy + fract(u_timer * 3.7) * 117.0) - 0.5) * 0.028;
  c += uFlash;
  c *= 1.0 - uFx.x;
  gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""




HAZE_FS = HEAD + CAM_U + """
uniform sampler2D uGBc;
uniform vec4 uLt[24];
uniform float uLtN;
uniform vec4 uLd[24];
uniform vec4 uLc[24];
uniform vec4 uHaze;
uniform vec4 uSun;
uniform vec4 uSunC;
uniform vec4 uFogC;
uniform vec2 u_res;
uniform float u_timer;
float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }
uniform vec2 uCut;
uniform vec4 uRay;
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec4 g = texture2D(uGBc, uv);
  float d = (g.r * 65280.0 + g.g * 255.0) / 65535.0 * 150.0;
  bool sky = d < 0.01;
  if (sky) d = 60.0;
  vec2 ndc = uv * 2.0 - 1.0 - uJit;
  vec3 dir = normalize(uCF + uCR * (ndc.x / uProj.x) - uCU * (ndc.y / uProj.y));
  float len = min(d / max(dot(dir, uCF), 0.05), 60.0);
  vec3 ro = uCP;
  if (uCut.x > 0.5 && sky) len = 0.0;
  if (uCut.x > 0.5 && dir.y < -0.01 && ro.y > uCut.y) {
    float t0 = (ro.y - uCut.y) / -dir.y;
    ro += dir * t0;
    len = max(len - t0, 0.0);
  }
  float st = len / 24.0;
  float j = ign(gl_FragCoord.xy + fract(u_timer * 7.0) * 113.0);
  vec3 acc = vec3(0.0);
  for (int k = 0; k < 24; k++) {
    vec3 p = ro + dir * ((float(k) + j) * st);
    for (int i = 0; i < 8; i++) {
      if (float(i) >= uHaze.y) break;
      vec3 lv = uLt[i].xyz - p;
      float d2 = dot(lv, lv);
      vec3 l = lv * inversesqrt(d2);
      float c = dot(-l, uLd[i].xyz);
      float pr = uLc[i].w < -1.5 ? max(c, 0.0) : smoothstep(uLd[i].w - 0.06, uLc[i].w + 0.02, c);
      float ph = 0.55 + 0.6 * pow(max(dot(dir, -l), 0.0), 3.0);
      acc += uLc[i].rgb * pr * ph / (d2 + 3.0);
    }
  }
  vec3 h = acc * st * uHaze.x + uHaze.z * vec3(0.004, 0.0047, 0.006) * len * uHaze.x;
  float sdp = dot(uSun.xyz, uCF);
  if (uRay.x > 0.0 && sdp > 0.05) {
    vec2 sn = vec2(dot(uSun.xyz, uCR) * uProj.x, -dot(uSun.xyz, uCU) * uProj.y) / sdp;
    vec2 suv = sn * 0.5 + 0.5;
    vec2 dl = (suv - uv) / 22.0;
    vec2 q = uv + dl * j;
    float ill = 0.0;
    float ws = 0.0;
    float w = 1.0;
    for (int k = 0; k < 22; k++) {
      if (q.x > 0.0 && q.y > 0.0 && q.x < 1.0 && q.y < 1.0) {
        vec4 gq = texture2D(uGBc, q);
        ill += step(gq.r + gq.g, 0.0001) * w;
      }
      ws += w;
      w *= 0.94;
      q += dl;
    }
    ill /= ws;
    float cs = max(dot(dir, uSun.xyz), 0.0);
    float fall = pow(cs, 5.0) * 0.55 + pow(cs, 30.0) * 0.45;
    float here = sky ? 0.35 : 1.0;
    h += uSunC.rgb * ill * fall * uRay.x * here * 0.5;
  }
  gl_FragColor = vec4(sqrt(clamp(h * 0.25, 0.0, 1.0)), 1.0);
}
"""

TAA_FS = HEAD + CAM_U + """
uniform sampler2D uCur;
uniform sampler2D uPrev;
uniform sampler2D uGBc;
uniform sampler2D uHz;
uniform vec3 uPC;
uniform vec3 uPRr;
uniform vec3 uPU;
uniform vec3 uPF;
uniform vec4 uPP;
uniform vec4 uTA;
uniform vec2 uTx;
uniform vec2 u_res;
vec3 dec(vec3 e) { return e * e * 4.0; }
vec3 tm(vec3 c) { return c / (1.0 + max(max(c.r, c.g), c.b)); }
vec3 itm(vec3 c) { return c / max(1.0 - max(max(c.r, c.g), c.b), 1e-3); }
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 hz = dec(texture2D(uHz, uv).rgb);
  vec3 c = tm(dec(texture2D(uCur, uv).rgb) + hz);
  vec3 m1 = c;
  vec3 m2 = c * c;
  for (int k = 0; k < 8; k++) {
    vec2 o = k == 0 ? vec2(1.0, 0.0) : k == 1 ? vec2(-1.0, 0.0) : k == 2 ? vec2(0.0, 1.0) : k == 3 ? vec2(0.0, -1.0) :
             k == 4 ? vec2(1.0, 1.0) : k == 5 ? vec2(-1.0, 1.0) : k == 6 ? vec2(1.0, -1.0) : vec2(-1.0, -1.0);
    vec3 n = tm(dec(texture2D(uCur, uv + o * uTx).rgb) + hz);
    m1 += n;
    m2 += n * n;
  }
  m1 /= 9.0;
  m2 /= 9.0;
  vec3 sd = sqrt(max(m2 - m1 * m1, 0.0));
  vec3 mn = m1 - sd * 1.25;
  vec3 mx = m1 + sd * 1.25;
  vec4 g = texture2D(uGBc, uv);
  float d = (g.r * 65280.0 + g.g * 255.0) / 65535.0 * 150.0;
  vec2 puv = uv;
  float a = 0.1;
  if (g.b < 0.75) {
    vec2 ndc = uv * 2.0 - 1.0 - uJit;
    vec3 wp = uCP + uCF * d + uCR * (ndc.x * d / uProj.x) - uCU * (ndc.y * d / uProj.y);
    vec3 r = wp - uPC;
    float pd = dot(r, uPF);
    vec2 pn = vec2(dot(r, uPRr) * uPP.x, -dot(r, uPU) * uPP.y) / max(pd, 1e-3) + uPP.zw;
    puv = pn * 0.5 + 0.5;
    if (pd < 0.01 || d < 0.01) a = 1.0;
  }
  bool fol = g.b > 0.35 && g.b < 0.45;
  if (fol) {
    a = max(a, 0.4);
    vec3 cm = (mx + mn) * 0.5;
    vec3 ch = (mx - mn) * 0.5 * 0.7;
    mn = cm - ch;
    mx = cm + ch;
  } else if (g.b > 0.25 && g.b < 0.75) a = max(a, 0.3);
  if (puv.x < 0.0 || puv.y < 0.0 || puv.x > 1.0 || puv.y > 1.0 || uTA.x > 0.5) a = 1.0;
  vec3 h = tm(dec(texture2D(uPrev, puv).rgb));
  h = clamp(h, mn, mx);
  vec3 o = itm(mix(h, c, a));
  gl_FragColor = vec4(sqrt(clamp(o * 0.25, 0.0, 1.0)), 1.0);
}
"""

EBLUR_FS = HEAD + """
uniform sampler2D uSrc;
uniform vec2 uDir;
uniform vec2 u_res;
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 tl = floor(uv * vec2(3.0, 2.0));
  vec2 lo = tl / vec2(3.0, 2.0) + uDir * 0.6;
  vec2 hi = (tl + 1.0) / vec2(3.0, 2.0) - uDir * 0.6;
  vec3 c = vec3(0.0);
  float w = 0.0;
  for (int i = -4; i <= 4; i++) {
    float fi = float(i);
    float k = exp(-fi * fi / 8.0);
    vec3 e = texture2D(uSrc, clamp(uv + uDir * fi, lo, hi)).rgb;
    c += e * e * k;
    w += k;
  }
  gl_FragColor = vec4(sqrt(c / w), 1.0);
}
"""


SKY_VS = HEAD + """
attribute vec3 aPos;
void main() {
  gl_Position = vec4(aPos.xy, 0.99999, 1.0);
}
"""

SKY_FS = HEAD + CAM_U + """
uniform float u_timer;
uniform vec4 uSun;
uniform vec4 uSunC;
uniform vec4 uSkyZ;
uniform vec4 uSkyH;
uniform vec4 uSkyG;
uniform vec4 uFog;
uniform vec4 uFogS;
""" + GATE + ENC + NOISE + """
float fbm(vec2 p) {
  float a = 0.5;
  float s = 0.0;
  for (int i = 0; i < 5; i++) {
    s += vnoise(p) * a;
    p = p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return s;
}
uniform vec4 uGB;
void main() {
  vec2 sc = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  if (sc.x < uWin.x || sc.y < uWin.y || sc.x > uWin.z || sc.y > uWin.w) discard;
  vec2 ndc = (sc - uVP.zw) / uVP.xy - uJit;
  vec3 dir = normalize(uCF + uCR * (ndc.x / uProj.x) - uCU * (ndc.y / uProj.y));
  float y = dir.y;
  float hz = pow(1.0 - max(y, 0.0), 4.0);
  vec3 col = mix(uSkyZ.rgb, uSkyH.rgb, hz);
  float sd = max(dot(dir, uSun.xyz), 0.0);
  col += uSunC.rgb * (pow(sd, 8.0) * 0.18 + pow(sd, 64.0) * 0.5) * (0.4 + 0.6 * hz);
  if (y > 0.0 && uSkyZ.w > 0.0) {
    vec2 cp = dir.xz / (y + 0.08) * 0.6 + vec2(u_timer * 0.006, u_timer * 0.002);
    float n = fbm(cp);
    float cov = smoothstep(1.0 - uSkyZ.w, 1.0 - uSkyZ.w + 0.35, n) * smoothstep(0.0, 0.18, y);
    vec3 cc = mix(uSkyH.rgb * 1.1, vec3(1.0, 0.98, 0.95) * (0.9 + uSunC.rgb * 0.15), 0.6 + 0.4 * sd);
    cc *= 0.75 + 0.35 * fbm(cp * 2.0 + 3.0);
    col = mix(col, cc, cov * 0.85);
  }
  col += uSunC.rgb * smoothstep(uSkyH.w, uSkyH.w + 0.0006, sd) * 40.0 * smoothstep(-0.02, 0.02, y);
  if (y < 0.0) col = mix(col, uSkyG.rgb, smoothstep(0.0, 0.12, -y));
  if (uFog.w > 0.0) {
    float fs = pow(sd, 8.0);
    vec3 fc = uFog.rgb * (1.0 + fs * 0.9);
    col = mix(col, fc, (1.0 - smoothstep(-0.02, 0.22, y)) * 0.85 * uFogS.z);
  }
  gl_FragColor = enc(col, 1.0);
}
"""


LUM_FS = HEAD + """
uniform sampler2D uSrc;
uniform sampler2D uPrev;
uniform vec4 uLA;
uniform vec2 u_res;
void main() {
  float acc = 0.0;
  float wt = 0.0;
  for (int j = 0; j < 7; j++) {
    for (int i = 0; i < 7; i++) {
      vec2 p = (vec2(float(i), float(j)) + 0.5) / 7.0;
      vec3 e = texture2D(uSrc, p).rgb;
      vec3 c = e * e * 4.0;
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      float w = 1.0 - 0.6 * length(p - 0.5);
      acc += log(max(l, 0.002)) * w;
      wt += w;
    }
  }
  float cur = exp(acc / wt);
  float pv = texture2D(uPrev, vec2(0.5)).r;
  float prev = pv * pv * 8.0;
  float o = uLA.y > 0.5 ? cur : mix(prev, cur, uLA.x);
  gl_FragColor = vec4(sqrt(clamp(o / 8.0, 0.0, 1.0)), 0.0, 0.0, 1.0);
}
"""


GRASS_VS = HEAD + CAM_U + PROJECT + WIND + """
uniform vec3 uPlr;
uniform vec4 uGT;
varying float vGust;
varying float vDry;
attribute vec4 aSeed;
attribute vec3 aCorner;
uniform float u_timer;
uniform sampler2D uTHM;
uniform vec4 uTHP;
uniform vec4 uTHR;
uniform vec4 uGR;
uniform vec4 uGS;
varying vec2 vUV;
varying vec3 vW;
varying float vFade;
varying float vShade;
void main() {
  float cell = uGS.x;
  vec2 cam = uCP.xz;
  vec2 base = cam + (fract(aSeed.xy - cam / cell) - 0.5) * cell;
  vec2 tc = (base - uTHP.xy) * uTHP.zw;
  vec4 hm = texture2D(uTHM, tc);
  float h = uTHR.x + (hm.r * 255.0 * 256.0 + hm.g * 255.0) / 65535.0 * uTHR.y;
  float dens = hm.b;
  float d = length(base - cam);
  float fade = 1.0 - smoothstep(uGS.y * 0.6, uGS.y, d);
  float keep = step(aSeed.w, dens * uGS.z) * step(0.0, tc.x) * step(tc.x, 1.0) * step(0.0, tc.y) * step(tc.y, 1.0);
  float k = floor(fract(aSeed.w * 7.13) * 3.0);
  if (fract(aSeed.z * 13.7 + aSeed.w * 3.1) < uGT.x) k = 3.0;
  float sz = (0.45 + 0.4 * aSeed.z) * fade * keep * uGS.w * (k > 2.5 ? 0.85 : 1.0);
  float ang = aSeed.z * 6.2831 + aCorner.z * 1.5708;
  vec3 right = vec3(cos(ang), 0.0, sin(ang));
  vec3 p = vec3(base.x, h - 0.04, base.y) + right * aCorner.x * sz * 0.6 + vec3(0.0, aCorner.y * sz, 0.0);
  float sw = aCorner.y * aCorner.y;
  vec3 wv = windAt(vec3(base.x, h, base.y), u_timer, aSeed.z * 6.2831);
  p.xz += wv.xz * 0.28 * sw * sz;
  vec2 away = base - uPlr.xz;
  float pd = length(away);
  float push = (1.0 - smoothstep(0.25, 0.95, pd)) * step(abs(h - uPlr.y), 1.0);
  p.xz += away / max(pd, 0.05) * push * 0.45 * sw * sz;
  p.y -= push * 0.35 * sw * sz;
  vGust = gust(base, u_timer);
  vDry = min(1.0, uGT.z * (0.95 + 0.3 * fract(aSeed.x * 31.7)));
  float qx = mod(k, 2.0);
  float qy = mod(floor(k / 2.0), 2.0);
  vec2 local = vec2(aCorner.x * 0.5 + 0.5, 1.0 - aCorner.y);
  vUV = uGR.xy + (vec2(qx, qy) + local) * 0.5 * uGR.zw;
  vW = p;
  vFade = fade * keep;
  vShade = 0.32 + 0.68 * pow(aCorner.y, 0.6);
  gl_Position = project(p);
}
"""

GRASS_FS = HEAD + """
uniform float u_timer;
uniform vec3 uCP;
uniform sampler2D uDA;
uniform sampler2D uDR;
uniform sampler2D uTLM;
uniform vec4 uTLMP;
uniform vec4 uFog;
uniform vec4 uFogS;
uniform vec3 uFogSun;
""" + GATE + ENC + """
varying vec2 vUV;
varying vec3 vW;
varying float vFade;
varying float vShade;
uniform vec4 uGB;
uniform vec3 uCF;
void gbOut(vec3 w) {
  float d = dot(w - uCP, uCF);
  float v = clamp(d / 150.0, 0.0, 1.0) * 65535.0;
  float hi = floor(v / 256.0);
  float lo = floor(v - hi * 256.0);
  gl_FragColor = vec4(hi / 255.0, lo / 255.0, 0.4, 1.0);
}
varying float vDry;
varying float vGust;
void main() {
  gate(vW);
  if (vFade < 0.01) discard;
  vec2 duv = vec2(vUV.x, vUV.y * (2.0 / 3.0));
  float al = texture2D(uDR, duv).b;
  if (al < 0.5) discard;
  if (uGB.x > 0.5) { gbOut(vW); return; }
  vec3 a = texture2D(uDA, duv).rgb;
  vec3 alb = a * a;
  vec2 cq = floor(vW.xz * 0.9);
  float h1 = fract(sin(dot(cq, vec2(12.9898, 78.233))) * 43758.5453);
  float h2 = fract(sin(dot(cq, vec2(39.346, 11.135))) * 24634.6345);
  alb *= mix(vec3(1.12, 1.02, 0.6), vec3(0.8, 0.95, 0.95), h1) * (0.78 + 0.4 * h2);
  alb = mix(alb, vec3(dot(alb, vec3(0.5, 0.4, 0.1))) * vec3(1.6, 1.25, 0.62), vDry);
  vec3 tl = texture2D(uTLM, (vW.xz - uTLMP.xy) * uTLMP.zw).rgb;
  vec3 E = tl * tl * 4.0;
  vec3 col = alb * E * vShade * 1.1 * (1.0 + vGust * 0.22 * vShade);
  float dist = length(uCP - vW);
  if (uFog.w > 0.0) {
    float fa = (1.0 - exp(-dist * uFog.w)) * uFogS.z;
    col = mix(col, uFog.rgb, fa);
  }
  gl_FragColor = enc(col, 1.0);
}
"""


def merge(vs, fs):
    have = set()
    for line in vs.splitlines():
        t = line.strip()
        if t.startswith("uniform "):
            have.add(t.rstrip(";").split()[-1].split("[")[0])
    add = []
    for line in fs.splitlines():
        t = line.strip()
        if t.startswith("uniform "):
            name = t.rstrip(";").split()[-1].split("[")[0]
            if name not in have:
                have.add(name)
                add.append(t)
    lines = vs.splitlines()
    return "\n".join(lines[:1] + add + lines[1:]) + "\n"


PORTAL_VS = HEAD + CAM_U + PROJECT + """
attribute vec3 aPos;
uniform vec3 uQC;
uniform vec3 uQR;
uniform vec3 uQU;
uniform vec3 uQN;
uniform vec4 uQS;
varying vec2 vL;
varying vec3 vW;
void main() {
  vL = aPos.xy;
  vec3 w = uQC + uQR * (aPos.x * uQS.x * uQS.z) + uQU * (aPos.y * uQS.y * uQS.z) + uQN * (0.004 + aPos.z);
  w += uQN * length(w - uCP) * 0.0006;
  vW = w;
  gl_Position = project(w);
}
"""

PORTAL_FS = HEAD + """
uniform float u_timer;
""" + GATE + ENC + NOISE + """
uniform sampler2D uView;
uniform vec4 uQM;
uniform vec3 uCol;
varying vec2 vL;
varying vec3 vW;
uniform vec3 uCP;

uniform vec4 uGB;
uniform vec3 uCF;
void gbOut(vec3 w) {
  float d = dot(w - uCP, uCF);
  float v = clamp(d / 150.0, 0.0, 1.0) * 65535.0;
  float hi = floor(v / 256.0);
  float lo = floor(v - hi * 256.0);
  gl_FragColor = vec4(hi / 255.0, lo / 255.0, uGB.y, 1.0);
}
void main() {
  gate(vW);
  float r = length(vL);
  if (uGB.x > 0.5) {
    if (r > 1.0) discard;
    gbOut(vW);
    return;
  }
  float t = u_timer;
  float ang = atan(vL.y, vL.x);
  float n1 = vnoise(vec2(ang * 2.5 + t * 1.7, r * 5.0 - t * 2.2));
  float n2 = vnoise(vec2(ang * 5.0 - t * 2.9, r * 9.0 + t * 1.3));
  float nn = n1 * 0.65 + n2 * 0.35;
  if (r > 1.0) {
    float g = exp(-(r - 1.0) * 16.0) * (0.6 + 0.9 * nn);
    if (g < 0.004) discard;
    gl_FragColor = vec4(sqrt(clamp(uCol * g * 0.4, 0.0, 1.0)), 0.0);
    return;
  }
  vec3 inside;
  if (uQM.x > 0.5) {
    vec2 suv = gl_FragCoord.xy / u_res;
    float wob = pow(r, 6.0) * 0.012;
    suv += vec2(cos(ang * 3.0 + t * 2.0), sin(ang * 2.0 - t * 1.7)) * wob;
    inside = texture2D(uView, suv).rgb;
    inside *= mix(0.62, 1.0, smoothstep(1.0, 0.55, r));
    if (uQM.y > 0.5) {
      inside = mix(inside, enc(uCol * (0.2 + nn * 0.4), 1.0).rgb, 0.55);
    }
  } else {
    float sw = vnoise(vec2(ang * 3.0 + r * 6.0 - t * 2.5, r * 4.0 - t)) ;
    vec3 c = uCol * (0.15 + 0.85 * pow(r, 2.5)) * (0.6 + sw * 0.8);
    inside = enc(c, 1.0).rgb;
  }
  float n3 = vnoise(vec2(ang * 9.0 - t * 4.0, t * 1.3));
  float edge = smoothstep(0.915, 0.965, r + (nn - 0.5) * 0.05 + (n3 - 0.5) * 0.03);
  float inner = smoothstep(0.72, 0.97, r) * 0.45;
  float hot = smoothstep(0.958, 0.985, r + (nn - 0.5) * 0.03);
  vec3 rim = uCol * (1.3 + nn * 1.4 + n3 * 0.8) + uCol * hot * 1.2 + vec3(hot * 0.25);
  vec3 rimE = enc(rim, 1.0).rgb;
  inside = mix(inside, enc(uCol * 0.9, 1.0).rgb, inner * (0.6 + 0.4 * nn));
  gl_FragColor = vec4(mix(inside, rimE, edge), 1.0);
}
"""


TEXT_VS = HEAD + """
attribute float aSlot;
attribute vec2 aCorner;
uniform vec4 uG[128];
uniform vec2 u_res;
uniform vec4 uTA;
varying vec2 vUV;
varying float vA;
void main() {
  vec4 g = uG[int(aSlot + 0.5)];
  if (g.w < 0.5) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vA = 0.0; vUV = vec2(0.0); return; }
  float asp = u_res.x / u_res.y;
  vec2 p = g.xy + aCorner * vec2(g.z * 0.6667, g.z);
  gl_Position = vec4(p.x / asp * 2.0 - 1.0, 1.0 - p.y * 2.0, 0.0, 1.0);
  float code = g.w - 32.0;
  vec2 cell = vec2(mod(code, 16.0), floor(code / 16.0));
  vUV = (cell + vec2(aCorner.x, 1.0 - aCorner.y)) / vec2(16.0, 6.0);
  vA = aSlot < 95.5 ? uTA.x : uTA.y;
}
"""

TEXT_FS = HEAD + """
uniform sampler2D uFont;
varying vec2 vUV;
varying float vA;
void main() {
  vec3 s = texture2D(uFont, vUV).rgb;
  float a = s.r + s.g * 0.75 * (1.0 - s.r);
  if (a * vA < 0.004) discard;
  gl_FragColor = vec4(vec3(s.r), a) * vA;
}
"""

SHADERS = {k: (merge(v, f), f) for k, (v, f) in {
    "text": (TEXT_VS, TEXT_FS),
    "portal": (PORTAL_VS, PORTAL_FS),
    "world": (WORLD_VS, WORLD_FS),
    "sky": (SKY_VS, SKY_FS),
    "part": (PART_VS, PART_FS),
    "bright": (QUAD_VS, BRIGHT_FS),
    "blur": (QUAD_VS, BLUR_FS),
    "eblur": (QUAD_VS, EBLUR_FS),
    "taa": (QUAD_VS, TAA_FS),
    "haze": (QUAD_VS, HAZE_FS),
    "comp": (QUAD_VS, COMP_FS),
    "lum": (QUAD_VS, LUM_FS),
    "grass": (GRASS_VS, GRASS_FS),
}.items()}
