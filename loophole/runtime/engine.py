@when_flag
def main():
    hide()
    init()
    make_rts()
    load_level(START_LEVEL)
    state = 3
    ttime = 0.3
    tdone = 1
    tafter = 1
    tl = timer()
    while True:
        tick()
        flow()
        render()


@warp
def init():
    FR = 0
    fps = 60
    frames = 0
    t0 = timer()
    TT = 0
    quality = QUALITY
    lastq = 0
    sens = 1.0
    lockon = 0
    lmb = 1
    api_ctl = 1
    api_cam = 0
    api_fov = FOV
    api_expo = 1
    api_fade = 0
    api_flash = 0
    api_walk = WALK
    api_jump = JUMPV
    api_grav = GRAV
    api_paused = 0
    api_goto = 0
    api_hold = 0
    api_look = 0
    api_used = 0
    api_cdist = 4
    api_cyaw = 0
    api_cpitch = 20
    cyaw = 0
    cpitch = 20
    snd_q.clear()
    mklist(KCOL, 8)
    jx = 0
    jy = 0
    gbm = 0
    vpx = 1
    vpy = 1
    vpox = 0
    vpoy = 0
    envdirty = 1
    costume("blank")
    tex_filter(9729)
    set_tex("uAtlas", "world", "atlas")
    set_tex("uAtlas2", "world", "atlas2")
    set_tex("uAtlas3", "world", "atlas3")
    api_vm = VMDEF
    set_tex("uProp", "world", "patlas")
    set_tex("uDA", "world", "dA")
    set_tex("uDN", "world", "dN")
    set_tex("uDR", "world", "dR")
    set_vec2("uPAt", "world", PAW, PAH)
    set_tex("uEnv", "world", "atlas")
    set_tex("uEnvB", "world", "atlas")
    set_tex("uEnvC", "world", "atlas")
    set_tex("uHist", "world", "atlas")
    set_tex("uPGB", "world", "atlas")
    set_vec4("uEnvP", "world", 0, 0, 0, 0)
    set_num("uLtN", "world", 0)
    set_num("uLtN", "part", 0)
    set_num("uShN", "world", 0)
    cull(0)


@warp
def mklist(L, n):
    pass


@warp
def make_rts():
    if quality == 1:
        RTW = 960
    elif quality == 2:
        RTW = 1280
    elif quality == 3:
        RTW = 1600
    else:
        RTW = 1920
    RTH = round(RTW * 9 / 16)
    create_rt("scene", RTW, RTH)
    tex_filter(9728)
    create_rt("gb0", RTW, RTH)
    create_rt("gb1", RTW, RTH)
    tex_filter(9729)
    create_rt("hz", round(RTW / 2), round(RTH / 2))
    create_rt("hz2", round(RTW / 2), round(RTH / 2))
    create_rt("hh0", RTW, RTH)
    create_rt("hh1", RTW, RTH)
    taareset = 1
    create_rt("b1", round(RTW / 4), round(RTH / 4))
    create_rt("b2", round(RTW / 4), round(RTH / 4))
    create_rt("b3", round(RTW / 8), round(RTH / 8))
    create_rt("b4", round(RTW / 8), round(RTH / 8))
    create_rt("env", 3 * ENVT, 2 * ENVT)
    create_rt("envb", 3 * ENVT / 2, ENVT)
    create_rt("enve", 3 * ENVT / 2, ENVT)
    create_rt("envc", 3 * ENVT / 4, ENVT / 2)
    create_rt("envd", 3 * ENVT / 4, ENVT / 2)
    envdirty = 1
    lastq = quality


@warp
def tick():
    dt = timer() - tl
    tl = timer()
    if dt > 0.05:
        dt = 0.05
    if dt < 0.001:
        dt = 0.001
    TT += dt
    frames += 1
    if timer() - t0 > 0.5:
        fps = round(frames / (timer() - t0))
        api_fps = fps
        frames = 0
        t0 = timer()
    locked = 0
    if plocked():
        locked = 1
    api_locked = locked
    mdx = 0
    mdy = 0
    if locked == 1:
        mdx = mouse_x()
        mdy = mouse_y()
    ke = 0
    if key("e"):
        if le == 0:
            ke = 1
        le = 1
    else:
        le = 0
    if mbtn(0) and locked == 1:
        if lmb == 0:
            ke = 1
        lmb = 1
    else:
        lmb = 0
    kr = 0
    if key("r"):
        if lr_ == 0:
            kr = 1
        lr_ = 1
    else:
        lr_ = 0
    pk = 0
    if key("p"):
        if lp_ == 0:
            pk = 1
        lp_ = 1
    else:
        lp_ = 0


@warp
def flow():
    if quality != lastq:
        make_rts()
    if api_goto > 0:
        gq_ = api_goto
        api_goto = 0
        begin(max(1, min(NLEV, round(gq_))))
    if state == 1 or state == 2:
        if locked == 0 and lockon == 0 and mouse_down():
            set_lock("true")
            lockon = 1
        if not mouse_down():
            lockon = 0
    if state == 1:
        if pk == 1 or (locked == 0 and wasl == 1) or api_paused == 1:
            state = 2
            api_paused = 1
            broadcast("paused")
        else:
            play_step()
    elif state == 2:
        if pk == 1 or (locked == 1 and wasl == 0) or api_paused == 0:
            state = 1
            api_paused = 0
            broadcast("resumed")
    elif state == 3:
        ttime += dt
        if ttime < 0.3:
            tfade = ttime / 0.3
        elif tdone == 0:
            tdone = 1
            tfade = 1
            if tnext == 0 - 1:
                respawn()
            else:
                load_level(tnext)
        else:
            tfade = max(0, 1 - (ttime - 0.4) / 0.35)
            if ttime > 0.75:
                tfade = 0
                state = tafter
                if tnext > 0:
                    broadcast("level start")
    wasl = locked
    sounds_step()


@warp
def begin(lv):
    if state != 3:
        tnext = lv
        tafter = 1
        ttime = 0
        tdone = 0
        state = 3


@warp
def die():
    if state == 1:
        play("fail")
        broadcast("player died")
        tnext = 0 - 1
        tafter = 1
        ttime = 0
        tdone = 0
        state = 3


@warp
def respawn():
    px = LSX[level]
    py = LSY[level]
    pz = LSZ[level]
    yaw = LSYAW[level]
    pitch = LSPIT[level]
    vx = 0
    vy = 0
    vz = 0
    onground = 0
    if api_hold > 0:
        OVX[api_hold] = 0
        OVY[api_hold] = 0
        OVZ[api_hold] = 0
    api_hold = 0
    api_out()


@warp
def sounds_step():
    for sqi in times(min(4, len(snd_q))):
        play(snd_q[1])
        snd_q.pop(1)


@warp
def load_level(lv):
    level = lv
    api_level = lv
    api_lname = LNAME[lv]
    lh0 = LH0[lv]
    lhn = LHN[lv]
    respawn()
    crouch = 0
    eyeh = EYE
    dip = 0
    dipv = 0
    bobp = 0
    roll = 0
    hsp = 0
    lvy = 0
    lastjump = 1
    ltime = 0
    api_time = 0
    vk = 0
    vkv = 0
    grk = 0
    lheld = 0
    vroll = 0
    shk = 0
    fovk = 0
    lvin = 0
    vin = 0
    vmswx = 0
    vmswy = 0
    vraise = 1
    holdk = 0
    lpx = px
    lpy = py
    lpz = pz
    objects_load(lv)
    triggers_load(lv)
    lights_load(lv)
    set_tex("uLM", "world", join("lm", lv))
    envdirty = 1
    taareset = 1
    set_vec4("uHaze", "world", LHZ[lv], LVN[lv], LHA[lv], 0)
    set_vec4("uHaze", "haze", LHZ[lv], LVN[lv], LHA[lv], 0)
    set_vec4("uGrade", "comp", LGR[lv], LGG[lv], LGB[lv], LSAT[lv])
    sky_load(lv)
    play("arrive")


@warp
def sky_load(lv):
    sb = (lv - 1) * 24 + 1
    set_vec4("uSun", "sky", SKY[sb], SKY[sb + 1], SKY[sb + 2], 1)
    set_vec4("uSunC", "sky", SKY[sb + 3], SKY[sb + 4], SKY[sb + 5], 1)
    set_vec4("uSkyZ", "sky", SKY[sb + 6], SKY[sb + 7], SKY[sb + 8], SKY[sb + 9])
    set_vec4("uSkyH", "sky", SKY[sb + 10], SKY[sb + 11], SKY[sb + 12], SKY[sb + 13])
    set_vec4("uSkyG", "sky", SKY[sb + 14], SKY[sb + 15], SKY[sb + 16], 0)
    set_vec4("uSun", "haze", SKY[sb], SKY[sb + 1], SKY[sb + 2], 1)
    set_vec4("uSunC", "haze", SKY[sb + 3], SKY[sb + 4], SKY[sb + 5], 1)
    set_vec4("uFogC", "haze", SKY[sb + 17], SKY[sb + 18], SKY[sb + 19], SKY[sb + 20])


@warp
def objects_load(lv):
    nobj = LON[lv]
    o0 = LO0[lv]
    obj_name.clear()
    obj_x.clear()
    obj_y.clear()
    obj_z.clear()
    obj_yaw.clear()
    obj_pitch.clear()
    obj_roll.clear()
    obj_scale.clear()
    obj_visible.clear()
    obj_solid.clear()
    obj_glow.clear()
    obj_open.clear()
    mklist(OVX, nobj)
    mklist(OVY, nobj)
    mklist(OVZ, nobj)
    mklist(OOPN, nobj)
    mklist(OPRS, nobj)
    mklist(OAX0, nobj)
    mklist(OAX1, nobj)
    mklist(OAY0, nobj)
    mklist(OAY1, nobj)
    mklist(OAZ0, nobj)
    mklist(OAZ1, nobj)
    mklist(OGRD, nobj)
    mklist(OPTH, nobj)
    obj_touch.clear()
    onplat = 0
    mklist(OPX, nobj)
    mklist(OPY, nobj)
    mklist(OPZ, nobj)
    for oi in rep(nobj):
        od = o0 + oi - 1
        obj_name.append(DNAME[od])
        obj_x.append(DX[od])
        obj_y.append(DY[od])
        obj_z.append(DZ[od])
        obj_yaw.append(DYAW[od])
        obj_pitch.append(DPITCH[od])
        obj_roll.append(DROLL[od])
        obj_scale.append(DSCALE[od])
        obj_visible.append(DVIS[od])
        obj_solid.append(DSOLID[od])
        obj_glow.append(DGLOW[od])
        obj_open.append(0)
        obj_touch.append(0)


@warp
def triggers_load(lv):
    trig_name.clear()
    trig_in.clear()
    for ti in rep(LTN[lv]):
        trig_name.append(TNAME[LT0[lv] + ti - 1])
        trig_in.append(0)


@warp
def lights_load(lv):
    light_name.clear()
    light_power.clear()
    mklist(LPWL, LLN[lv])
    lk = LL0[lv]
    for li in rep(LLN[lv]):
        light_name.append(LNM[lk])
        light_power.append(1)
        LPWL[li] = 1
        set_arr4(li, "uLt", "world", LTX[lk], LTY[lk], LTZ[lk], LTW[lk])
        set_arr4(li, "uLd", "world", LDDX[lk], LDDY[lk], LDDZ[lk], LDDW[lk])
        set_arr4(li, "uLc", "world", LCR[lk], LCG[lk], LCB[lk], LCW[lk])
        set_arr4(li, "uLf", "world", LDYN[lk], 0, 0, 0)
        set_arr4(li, "uLt", "part", LTX[lk], LTY[lk], LTZ[lk], LTW[lk])
        set_arr4(li, "uLd", "part", LDDX[lk], LDDY[lk], LDDZ[lk], LDDW[lk])
        set_arr4(li, "uLc", "part", LCR[lk], LCG[lk], LCB[lk], LCW[lk])
        set_arr4(li, "uLt", "haze", LTX[lk], LTY[lk], LTZ[lk], LTW[lk])
        set_arr4(li, "uLd", "haze", LDDX[lk], LDDY[lk], LDDZ[lk], LDDW[lk])
        set_arr4(li, "uLc", "haze", LCR[lk], LCG[lk], LCB[lk], LCW[lk])
        lk += 1
    set_num("uLtN", "world", LLN[lv])
    set_num("uLtN", "part", LLN[lv])
    set_num("uLtN", "haze", LLN[lv])


@warp
def lights_step():
    lk = LL0[level]
    for li in rep(LLN[level]):
        lpw = light_power[li]
        if lpw != LPWL[li]:
            LPWL[li] = lpw
            set_arr4(li, "uLc", "world", LCR[lk] * lpw, LCG[lk] * lpw, LCB[lk] * lpw, LCW[lk])
            set_arr4(li, "uLc", "part", LCR[lk] * lpw, LCG[lk] * lpw, LCB[lk] * lpw, LCW[lk])
            set_arr4(li, "uLc", "haze", LCR[lk] * lpw, LCG[lk] * lpw, LCB[lk] * lpw, LCW[lk])
        lk += 1


@warp
def api_in():
    if api_px != lpx or api_py != lpy or api_pz != lpz:
        px = api_px
        py = api_py
        pz = api_pz
        vx = 0
        vy = 0
        vz = 0
    if api_yaw != lyaw:
        yaw = api_yaw
    if api_pitch != lpitch:
        pitch = max(-89, min(89, api_pitch))


@warp
def api_out():
    api_px = round(px * 1000) / 1000
    api_py = round(py * 1000) / 1000
    api_pz = round(pz * 1000) / 1000
    api_yaw = round(yaw * 100) / 100
    api_pitch = round(pitch * 100) / 100
    lpx = api_px
    lpy = api_py
    lpz = api_pz
    lyaw = api_yaw
    lpitch = api_pitch
    api_speed = round(hsp * 100) / 100
    api_ground = onground


@warp
def play_step():
    ltime += dt
    api_time = round(ltime * 100) / 100
    if kr == 1:
        begin(level)
        return
    api_in()
    lights_step()
    objects_prep()
    if api_ctl == 1:
        look()
    else:
        mdx = 0
        mdy = 0
    player_move()
    objects_step()
    feel()
    if FR % 2 == 0:
        aim_ray()
    if ke == 1 and api_ctl == 1:
        use_key()
    buttons_step()
    triggers_step()
    if py < LKILL[level]:
        die()
    api_out()


@warp
def look():
    sk = SENS * sens
    lkx = mdx * sk
    lky = mdy * sk
    if key("left arrow"):
        lkx += 0 - 140 * dt
    if key("right arrow"):
        lkx += 140 * dt
    if key("up arrow"):
        lky += 100 * dt
    if key("down arrow"):
        lky += 0 - 100 * dt
    if api_cam == 2:
        cyaw += lkx
        cpitch = max(-30, min(75, cpitch - lky))
    elif api_cam == 3:
        cyaw += lkx * 0.5
    else:
        yaw += lkx
        pitch = max(-89, min(89, pitch + lky))
    vmswx += (0 - mdx * 0.0012 - vmswx) * min(1, dt * 10)
    vmswy += (0 - mdy * 0.0012 - vmswy) * min(1, dt * 10)


@warp
def player_move():
    mvf = 0
    mvr = 0
    if api_ctl == 1:
        if key("w"):
            mvf += 1
        if key("s"):
            mvf += -1
        if key("d"):
            mvr += 1
        if key("a"):
            mvr += -1
    myaw = yaw
    if api_cam == 2 or api_cam == 3:
        myaw = cyaw
    mwx = sin(myaw) * mvf + cos(myaw) * mvr
    mwz = 0 - cos(myaw) * mvf + sin(myaw) * mvr
    mwl = sqrt(mwx * mwx + mwz * mwz)
    if mwl > 0.001:
        mwx = mwx / mwl
        mwz = mwz / mwl
        if api_cam == 2 or api_cam == 3:
            atan2_(mwx, 0 - mwz)
            ydiff = (at - yaw + 540) % 360 - 180
            yaw += ydiff * min(1, dt * 10)
    wsp = api_walk
    if api_ctl == 1 and (key("c") or key("shift")):
        crouch = 1
        wsp = api_walk * 0.4
    elif crouch == 1:
        crouch = 0
    if mwl < 0.001:
        wsp = 0
    if api_ctl == 1 and onground == 1 and key("space") and lastjump > 0.08:
        vy = api_jump
        onground = 0
        lastjump = 0
        play("jump")
    lastjump += dt
    if onground == 1:
        msp = sqrt(vx * vx + vz * vz)
        if msp > 0.0001:
            mctl = msp
            if mctl < STOPSPD:
                mctl = STOPSPD
            mns = msp - mctl * FRIC * dt
            if mns < 0:
                mns = 0
            vx = vx * mns / msp
            vz = vz * mns / msp
        accel(mwx, mwz, wsp, wsp, ACCEL)
    else:
        mcap = wsp
        if mcap > AIRCAP:
            mcap = AIRCAP
        accel(mwx, mwz, mcap, wsp, AIRACC)
    vy = max(-40, vy - api_grav * dt)
    vent_at(px, py, pz)
    if vin > 0:
        vy = min(7.5 * vin, vy + (api_grav + 30 * (vfall - 0.3)) * dt * vin)
        vy = vy * (1 - min(1, dt * 3))
        if onground == 0:
            vx = vx * (1 - min(1, dt * 2.5))
            vz = vz * (1 - min(1, dt * 2.5))
        if lvin == 0:
            play("whoosh")
    lvin = ceil(vin)
    bx = px
    by = py
    bz = pz
    bvx = vx
    bvy = vy
    bvz = vz
    bhx = PW
    bhy = PHT
    if crouch == 1:
        bhy = PHTC
    bself = 0
    if onplat > 0:
        bx += OAX0[onplat] - OPX[onplat]
        by += OAY0[onplat] - OPY[onplat]
        bz += OAZ0[onplat] - OPZ[onplat]
    move_body()
    px = bx
    py = by
    pz = bz
    vx = bvx
    vy = bvy
    vz = bvz
    onplat = bplat
    if bground == 1 and onground == 0 and lvy < -3.5:
        dip = min(0.22, (0 - lvy) * 0.018)
        shk = max(shk, min(1, (0 - lvy - 5) * 0.07))
        if lvy < -8:
            play("land")
    lvy = vy
    if bground == 0:
        lvy = bvy
    onground = bground
    hsp = sqrt(vx * vx + vz * vz)
    if onground == 1 and hsp > 0.5:
        bobp += hsp * dt * 2.2
        if hsp > 1.6:
            stp = floor(bobp / 3.14159)
            if stp != lstp:
                lstp = stp
                play(join("step", random(1, 5)))
    else:
        bobp = bobp * (1 - min(1, dt * 6))
    airk += (1 - onground - airk) * min(1, dt * 9)
    crk += (crouch - crk) * min(1, dt * 10)
    dipv += (0 - dip * 40 - dipv * 9) * dt
    dip += dipv * dt
    if dip < 0:
        dip = 0
        dipv = 0
    eyet = EYE
    if crouch == 1:
        eyet = EYEC
    eyeh += (eyet - eyeh) * min(1, dt * 12)
    rollt = 0 - (vx * cos(yaw) + vz * sin(yaw)) * 0.45
    rollt = max(-2.5, min(2.5, rollt))
    roll += (rollt - roll) * min(1, dt * 8)
    if bkill == 1:
        die()


@warp
def atan2_(ay, ax):
    if ax > 0:
        at = atan(ay / ax)
    elif ax < 0:
        if ay >= 0:
            at = atan(ay / ax) + 180
        else:
            at = atan(ay / ax) - 180
    elif ay > 0:
        at = 90
    elif ay < 0:
        at = -90
    else:
        at = 0


@warp
def accel(dx, dz, cap, full, acc):
    acur = vx * dx + vz * dz
    aadd = cap - acur
    if aadd > 0:
        aas = acc * full * dt
        if aas > aadd:
            aas = aadd
        vx += aas * dx
        vz += aas * dz


@warp
def feel():
    vkv += (0 - vk * 240 - vkv * 19) * dt
    vk += vkv * dt
    if api_hold > 0:
        hheld = 1
    else:
        hheld = 0
    if hheld != lheld:
        if hheld == 1:
            grk = 1
        else:
            grk = -0.7
        lheld = hheld
    grk += (0 - grk) * min(1, dt * 7)
    vlat = vx * cos(yaw) + vz * sin(yaw)
    vroll += (0 - vlat * 1.1 - vroll) * min(1, dt * 7)
    shk = max(0, shk - dt * 2.2)
    fspd = sqrt(vx * vx + vy * vy + vz * vz)
    fovt = max(0, min(16, (fspd - 9) * 0.9))
    fovk += (fovt - fovk) * min(1, dt * 5)


@warp
def vent_at(x, y, z):
    vin = 0
    vfall = 0
    vj = LV0[level]
    for vji in times(LVNN[level]):
        if x > VX0[vj] and x < VX1[vj] and z > VZ0[vj] and z < VZ1[vj] and y > VY0[vj] - 0.3 and y < VY1[vj]:
            vin = VPW[vj]
            vfall = max(0, min(1, (VY1[vj] - y) / 4))
        vj += 1


@warp
def obj_basis(k):
    ocy_ = cos(obj_yaw[k])
    osy_ = sin(obj_yaw[k])
    ocp_ = cos(obj_pitch[k])
    osp_ = sin(obj_pitch[k])
    ocr_ = cos(obj_roll[k])
    osr_ = sin(obj_roll[k])
    yx_ = 0 - osy_ * osp_
    yy_ = ocp_
    yz_ = ocy_ * osp_
    bzx = 0 - osy_ * ocp_
    bzy = 0 - osp_
    bzz = ocy_ * ocp_
    bxx = ocy_ * ocr_ + yx_ * osr_
    bxy = yy_ * osr_
    bxz = osy_ * ocr_ + yz_ * osr_
    byx = yx_ * ocr_ - ocy_ * osr_
    byy = yy_ * ocr_
    byz = yz_ * ocr_ - osy_ * osr_
    osc_ = obj_scale[k]
    od_ = LO0[level] + k - 1
    osx_ = DSX[od_] * osc_
    osy2 = DSY[od_] * osc_
    osz_ = DSZ[od_] * osc_


@warp
def objects_prep():
    for ok_ in rep(nobj):
        od = LO0[level] + ok_ - 1
        obj_basis(ok_)
        ocx = DBCX[od] * osx_
        ocy = DBCY[od] * osy2
        ocz = DBCZ[od] * osz_
        ohx = DBX[od] * osx_
        ohy = DBY[od] * osy2
        ohz = DBZ[od] * osz_
        wcx = obj_x[ok_] + bxx * ocx + byx * ocy + bzx * ocz
        wcy = obj_y[ok_] + bxy * ocx + byy * ocy + bzy * ocz + OOPN[ok_] * DSLIDE[od]
        wcz = obj_z[ok_] + bxz * ocx + byz * ocy + bzz * ocz
        ehx = abs(bxx) * ohx + abs(byx) * ohy + abs(bzx) * ohz
        ehy = abs(bxy) * ohx + abs(byy) * ohy + abs(bzy) * ohz
        ehz = abs(bxz) * ohx + abs(byz) * ohy + abs(bzz) * ohz
        OPX[ok_] = OAX0[ok_]
        OPY[ok_] = OAY0[ok_]
        OPZ[ok_] = OAZ0[ok_]
        OAX0[ok_] = wcx - ehx
        OAX1[ok_] = wcx + ehx
        OAY0[ok_] = wcy - ehy
        OAY1[ok_] = wcy + ehy
        OAZ0[ok_] = wcz - ehz
        OAZ1[ok_] = wcz + ehz


@warp
def objects_step():
    for ok_ in rep(nobj):
        od = LO0[level] + ok_ - 1
        if DKIND[od] == 1:
            otgt = obj_open[ok_]
            if OOPN[ok_] < otgt:
                OOPN[ok_] = min(otgt, OOPN[ok_] + dt * DOSP[od])
            elif OOPN[ok_] > otgt:
                OOPN[ok_] = max(otgt, OOPN[ok_] - dt * DOSP[od])
        if DSPIN[od] != 0:
            obj_yaw[ok_] = (obj_yaw[ok_] + DSPIN[od] * dt) % 360
        if DPN[od] > 1 and obj_visible[ok_] == 1:
            path_step(ok_)
        if obj_visible[ok_] == 1:
            ttch = 0
            if px + PW > OAX0[ok_] - 0.15 and px - PW < OAX1[ok_] + 0.15 and pz + PW > OAZ0[ok_] - 0.15 and pz - PW < OAZ1[ok_] + 0.15 and py < OAY1[ok_] + 0.1 and py + PHT > OAY0[ok_] - 0.1:
                ttch = 1
            if ttch != obj_touch[ok_]:
                obj_touch[ok_] = ttch
                if ttch == 1:
                    broadcast(join("touch ", obj_name[ok_]))
                    if DCOLL[od] == 1:
                        obj_visible[ok_] = 0
                        play("pickup")
                        broadcast(join("collect ", obj_name[ok_]))
        if api_hold == ok_:
            hold_step(ok_)
        elif DPHYS[od] == 1 and obj_visible[ok_] == 1:
            phys_step(ok_)


@warp
def path_step(k):
    od = LO0[level] + k - 1
    pn_ = DPN[od]
    pp0 = DP0[od]
    OPTH[k] = OPTH[k] + dt * DPSP[od]
    ptot = PLEN[pp0 + pn_ - 1]
    if DPLOOP[od] == 1:
        ptot = PLEN[pp0 + pn_ - 1] + PCLOSE[pp0 + pn_ - 1]
        pd = OPTH[k] % ptot
    else:
        pd = OPTH[k] % (ptot * 2)
        if pd > ptot:
            pd = ptot * 2 - pd
    pi_ = 0
    for pq in rep(pn_ - 1):
        if PLEN[pp0 + pq] < pd:
            pi_ = pq
    pa_ = pp0 + pi_
    pb_ = pp0 + pi_ + 1
    if pi_ >= pn_ - 1:
        pb_ = pp0
    pseg = PLEN[pb_] - PLEN[pa_]
    if pb_ == pp0:
        pseg = PCLOSE[pa_]
    pt_ = 0
    if pseg > 0.0001:
        pt_ = (pd - PLEN[pa_]) / pseg
    pt_ = max(0, min(1, pt_))
    obj_x[k] = PWX[pa_] + (PWX[pb_] - PWX[pa_]) * pt_
    obj_y[k] = PWY[pa_] + (PWY[pb_] - PWY[pa_]) * pt_
    obj_z[k] = PWZ[pa_] + (PWZ[pb_] - PWZ[pa_]) * pt_
    pdx = PWX[pb_] - PWX[pa_]
    pdz = PWZ[pb_] - PWZ[pa_]
    if DPLOOP[od] == 0 and OPTH[k] % (ptot * 2) > ptot:
        pdx = 0 - pdx
        pdz = 0 - pdz
    if DPFACE[od] == 1 and abs(pdx) + abs(pdz) > 0.001:
        atan2_(pdx, 0 - pdz)
        pyd = (at - obj_yaw[k] + 540) % 360 - 180
        obj_yaw[k] = obj_yaw[k] + pyd * min(1, dt * 6)


@warp
def hold_step(k):
    od = LO0[level] + k - 1
    htx = px + sin(yaw) * cos(pitch) * HOLDD
    hty = py + eyeh + sin(pitch) * HOLDD
    htz = pz - cos(yaw) * cos(pitch) * HOLDD
    hcy = (OAY0[k] + OAY1[k]) / 2 - obj_y[k]
    hvx = (htx - (OAX0[k] + OAX1[k]) / 2) * 14
    hvy = (hty - (OAY0[k] + OAY1[k]) / 2) * 14
    hvz = (htz - (OAZ0[k] + OAZ1[k]) / 2) * 14
    hvl = sqrt(hvx * hvx + hvy * hvy + hvz * hvz)
    if hvl > 16:
        hvx = hvx * 16 / hvl
        hvy = hvy * 16 / hvl
        hvz = hvz * 16 / hvl
    OVX[k] = hvx
    OVY[k] = hvy
    OVZ[k] = hvz
    obj_yaw[k] = obj_yaw[k] + (yaw - obj_yaw[k]) * min(1, dt * 8)
    body_obj(k)
    hd2 = ((OAX0[k] + OAX1[k]) / 2 - htx) * ((OAX0[k] + OAX1[k]) / 2 - htx) + ((OAZ0[k] + OAZ1[k]) / 2 - htz) * ((OAZ0[k] + OAZ1[k]) / 2 - htz)
    if hd2 > 4:
        hfar += dt
        if hfar > 0.35:
            api_hold = 0
            play("release")
    else:
        hfar = 0


@warp
def phys_step(k):
    OVY[k] = max(-40, OVY[k] - api_grav * dt)
    vent_at((OAX0[k] + OAX1[k]) / 2, OAY0[k], (OAZ0[k] + OAZ1[k]) / 2)
    if vin > 0:
        OVY[k] = min(7 * vin, OVY[k] + (api_grav + 30 * (vfall - 0.3)) * dt * vin)
        OVY[k] = OVY[k] * (1 - min(1, dt * 3))
    cpre = OVY[k]
    body_obj(k)
    if bground == 1:
        if cpre < -3.2:
            play("impact")
        OVX[k] = OVX[k] * (1 - min(1, dt * 8))
        OVZ[k] = OVZ[k] * (1 - min(1, dt * 8))
    if bkill == 1 or OAY0[k] < LKILL[level]:
        od = LO0[level] + k - 1
        obj_x[k] = DX[od]
        obj_y[k] = DY[od] + 0.5
        obj_z[k] = DZ[od]
        OVX[k] = 0
        OVY[k] = 0
        OVZ[k] = 0
        objects_prep()


@warp
def body_obj(k):
    obx0 = (OAX0[k] + OAX1[k]) / 2
    obz0 = (OAZ0[k] + OAZ1[k]) / 2
    oby0 = OAY0[k]
    bx = obx0
    by = oby0
    bz = obz0
    bvx = OVX[k]
    bvy = OVY[k]
    bvz = OVZ[k]
    bhx = max(OAX1[k] - OAX0[k], OAZ1[k] - OAZ0[k]) / 2
    bhy = OAY1[k] - OAY0[k]
    bself = k
    move_body()
    obj_x[k] = obj_x[k] + bx - obx0
    obj_y[k] = obj_y[k] + by - oby0
    obj_z[k] = obj_z[k] + bz - obz0
    OAX0[k] = OAX0[k] + bx - obx0
    OAX1[k] = OAX1[k] + bx - obx0
    OAY0[k] = OAY0[k] + by - oby0
    OAY1[k] = OAY1[k] + by - oby0
    OAZ0[k] = OAZ0[k] + bz - obz0
    OAZ1[k] = OAZ1[k] + bz - obz0
    OVX[k] = bvx
    OVY[k] = bvy
    OVZ[k] = bvz
    OGRD[k] = bground


@warp
def use_key():
    if api_hold > 0:
        api_hold = 0
        play("release")
        return
    if api_look > 0 and lookd < USED:
        od = LO0[level] + api_look - 1
        if DCARRY[od] == 1:
            api_hold = api_look
            hfar = 0
            play("pickup")
        elif DUSE[od] == 1:
            api_used = api_look
            play("click")
            broadcast(join("use ", obj_name[api_look]))


@warp
def buttons_step():
    for bk in rep(nobj):
        od = LO0[level] + bk - 1
        if DKIND[od] == 2 and obj_visible[bk] == 1:
            bcx_ = obj_x[bk]
            bcy_ = obj_y[bk]
            bcz_ = obj_z[bk]
            bpr = 0
            if abs(px - bcx_) < 0.95 and abs(pz - bcz_) < 0.95 and abs(py - bcy_ - 0.2) < 0.35:
                bpr = 1
            for bj in rep(nobj):
                odj = LO0[level] + bj - 1
                if DPHYS[odj] == 1 and api_hold != bj and obj_visible[bj] == 1:
                    if abs((OAX0[bj] + OAX1[bj]) / 2 - bcx_) < 0.95 and abs((OAZ0[bj] + OAZ1[bj]) / 2 - bcz_) < 0.95 and abs(OAY0[bj] - bcy_ - 0.2) < 0.4:
                        bpr = 1
            if bpr != OPRS[bk]:
                OPRS[bk] = bpr
                if DLNK[od] > 0:
                    obj_open[DLNK[od]] = bpr
                if bpr == 1:
                    play("button")
                    if DLNK[od] > 0:
                        play("door_open")
                    broadcast(join("press ", obj_name[bk]))
                else:
                    play("unpress")
                    if DLNK[od] > 0:
                        play("door_close")
                    broadcast(join("release ", obj_name[bk]))
            OOPN[bk] = OOPN[bk] + (OPRS[bk] - OOPN[bk]) * min(1, dt * 8)


@warp
def triggers_step():
    tk = LT0[level]
    for ti in rep(LTN[level]):
        tin = 0
        if px > TX0[tk] and px < TX1[tk] and pz > TZ0[tk] and pz < TZ1[tk] and py + 0.9 > TY0[tk] and py < TY1[tk]:
            tin = 1
        if tin != trig_in[ti]:
            trig_in[ti] = tin
            if tin == 1:
                broadcast(join("enter ", TNAME[tk]))
                if TKIND[tk] == 1:
                    die()
                elif TKIND[tk] == 2:
                    play("success")
                    if TARG[tk] > 0:
                        begin(TARG[tk])
                    elif level < NLEV:
                        begin(level + 1)
                    else:
                        broadcast("game complete")
            else:
                broadcast(join("leave ", TNAME[tk]))
        tk += 1


@warp
def aim_ray():
    sex = px
    sey = py + eyeh
    sez = pz
    sdx = sin(yaw) * cos(pitch)
    sdy = sin(pitch)
    sdz = 0 - cos(yaw) * cos(pitch)
    if api_cam != 0:
        sex = ccx
        sey = ccy
        sez = ccz
        sdx = cfx
        sdy = cfy
        sdz = cfz
    ray_world(sex, sey, sez, sdx, sdy, sdz)
    api_look = 0
    lookd = rwt
    for ak in rep(nobj):
        if obj_visible[ak] == 1 and api_hold != ak:
            box_ray((OAX0[ak] + OAX1[ak]) / 2, (OAY0[ak] + OAY1[ak]) / 2, (OAZ0[ak] + OAZ1[ak]) / 2, (OAX1[ak] - OAX0[ak]) / 2, (OAY1[ak] - OAY0[ak]) / 2, (OAZ1[ak] - OAZ0[ak]) / 2, sex, sey, sez, sdx, sdy, sdz)
            if brres < lookd:
                lookd = brres
                api_look = ak
    if api_cam != 0 and api_look > 0:
        lookd = sqrt(((OAX0[api_look] + OAX1[api_look]) / 2 - px) * ((OAX0[api_look] + OAX1[api_look]) / 2 - px) + ((OAZ0[api_look] + OAZ1[api_look]) / 2 - pz) * ((OAZ0[api_look] + OAZ1[api_look]) / 2 - pz))
    api_lookd = round(lookd * 100) / 100


@warp
def box_ray(bcx, bcy, bcz, bhx_, bhy_, bhz_, ox, oy, oz, dx, dy, dz):
    brt = 999
    brlo = 0
    brhi = 999
    brok = 1
    for bra in rep(3):
        if bra == 1:
            bro = ox
            brd = dx
            brc = bcx
            brh = bhx_
        elif bra == 2:
            bro = oy
            brd = dy
            brc = bcy
            brh = bhy_
        else:
            bro = oz
            brd = dz
            brc = bcz
            brh = bhz_
        if abs(brd) < 0.00001:
            if abs(bro - brc) > brh:
                brok = 0
        else:
            brt1 = (brc - brh - bro) / brd
            brt2 = (brc + brh - bro) / brd
            if brt1 < brt2:
                brlo = max(brlo, brt1)
                brhi = min(brhi, brt2)
            else:
                brlo = max(brlo, brt2)
                brhi = min(brhi, brt1)
    if brok == 1 and brlo < brhi:
        brt = brlo
    brres = brt


@warp
def move_body():
    bground = 0
    bkill = 0
    bplat = 0
    mb_axis(1)
    mb_axis(2)
    mb_axis(3)
    if HASTER == 1:
        terrain_ground()


@warp
def terrain_ground():
    if LTER[level] == 1:
        tgx = (bx - TOX[level]) / TST[level]
        tgz = (bz - TOZ[level]) / TST[level]
        if tgx >= 0 and tgz >= 0 and tgx < TNX[level] - 1 and tgz < TNZ[level] - 1:
            tix = floor(tgx)
            tiz = floor(tgz)
            tfx = tgx - tix
            tfz = tgz - tiz
            tb = TH0[level] + tiz * TNX[level] + tix
            th = (THT[tb] * (1 - tfx) + THT[tb + 1] * tfx) * (1 - tfz) + (THT[tb + TNX[level]] * (1 - tfx) + THT[tb + TNX[level] + 1] * tfx) * tfz
            if by < th + 0.02 and by > th - 1.2 and bvy <= 0.5:
                by = th
                if bvy < 0:
                    bvy = 0
                bground = 1


@warp
def mb_axis(ax):
    mstepy = -9999
    if ax == 1:
        mbn = bx + bvx * dt
        mbv = bvx
    elif ax == 2:
        mbn = by + bvy * dt
        mbv = bvy
    else:
        mbn = bz + bvz * dt
        mbv = bvz
    mbk = lh0
    for mbi in times(lhn):
        if HAX[mbk] == ax:
            if ax == 1:
                mbo = (by < HV1[mbk] and by + bhy > HV0[mbk] and bz - bhx < HU1[mbk] and bz + bhx > HU0[mbk]) + 0
                mblo = bx - bhx
                mbhi = bx + bhx
                mbnlo = mbn - bhx
                mbnhi = mbn + bhx
            elif ax == 2:
                mbo = (bx - bhx < HU1[mbk] and bx + bhx > HU0[mbk] and bz - bhx < HV1[mbk] and bz + bhx > HV0[mbk]) + 0
                mblo = by
                mbhi = by + bhy
                mbnlo = mbn
                mbnhi = mbn + bhy
            else:
                mbo = (bx - bhx < HU1[mbk] and bx + bhx > HU0[mbk] and by < HV1[mbk] and by + bhy > HV0[mbk]) + 0
                mblo = bz - bhx
                mbhi = bz + bhx
                mbnlo = mbn - bhx
                mbnhi = mbn + bhx
            mstp = 0
            if mbo == 1 and ax != 2 and bself == 0 and onground == 1:
                mbc = bx
                if ax == 3:
                    mbc = bz
                if HV1[mbk] - by < STEPH and HV1[mbk] - by > 0.01 and abs(HPL[mbk] - mbc) < bhx + 0.12 and HSG[mbk] * mbv < 0:
                    mstp = 1
                    if HV1[mbk] > mstepy:
                        mstepy = HV1[mbk]
            if mbo == 1 and mstp == 0:
                mbp = HPL[mbk]
                if HSG[mbk] < 0 and mbv > 0 and mbhi < mbp + 0.02 and mbnhi > mbp:
                    mbd = mbp - mbnhi - 0.0005
                    mbn += mbd
                    mbnlo += mbd
                    mbnhi += mbd
                    mbv = 0
                elif HSG[mbk] > 0 and mbv < 0 and mblo > mbp - 0.02 and mbnlo < mbp:
                    mbd = mbp - mbnlo + 0.0005
                    mbn += mbd
                    mbnlo += mbd
                    mbnhi += mbd
                    mbv = 0
                    if ax == 2:
                        bground = 1
                        if HKILL[mbk] == 1:
                            bkill = 1
        mbk += 1
    solids_axis(ax)
    if mstepy > -9999 and mstepy > by:
        by = mstepy + 0.001
    if ax == 1:
        bx = mbn
        bvx = mbv
    elif ax == 2:
        by = mbn
        bvy = mbv
    else:
        bz = mbn
        bvz = mbv


@warp
def solids_axis(ax):
    for so in rep(nobj):
        if so != bself and obj_solid[so] == 1 and obj_visible[so] == 1 and not (bself == 0 and so == api_hold) and not (bself > 0 and api_hold == bself) and OOPN[so] < 0.9:
            sox0 = OAX0[so]
            sox1 = OAX1[so]
            soy0 = OAY0[so]
            soy1 = OAY1[so]
            soz0 = OAZ0[so]
            soz1 = OAZ1[so]
            if ax == 1:
                soo = (by < soy1 and by + bhy > soy0 and bz - bhx < soz1 and bz + bhx > soz0) + 0
                sop0 = sox0
                sop1 = sox1
            elif ax == 2:
                soo = (bx - bhx < sox1 and bx + bhx > sox0 and bz - bhx < soz1 and bz + bhx > soz0) + 0
                sop0 = soy0
                sop1 = soy1
            else:
                soo = (bx - bhx < sox1 and bx + bhx > sox0 and by < soy1 and by + bhy > soy0) + 0
                sop0 = soz0
                sop1 = soz1
            if soo == 1:
                if ax != 2 and bself == 0 and onground == 1 and soy1 - by < STEPH and soy1 - by > 0.01:
                    if soy1 > mstepy:
                        mstepy = soy1
                        bplat = so
                elif mbv > 0 and mbhi < sop0 + 0.02 and mbnhi > sop0:
                    mbd = sop0 - mbnhi - 0.0005
                    mbn += mbd
                    mbnlo += mbd
                    mbnhi += mbd
                    mbv = 0
                elif mbv < 0 and mblo > sop1 - 0.02 and mbnlo < sop1:
                    mbd = sop1 - mbnlo + 0.0005
                    mbn += mbd
                    mbnlo += mbd
                    mbnhi += mbd
                    mbv = 0
                    if ax == 2:
                        bground = 1
                        bplat = so


@warp
def render():
    FR += 1
    pick_cam()
    frame_uniforms()
    if envdirty == 1:
        probe_all()
        pick_cam()
    wx0 = -1
    wy0 = -1
    wx1 = 1
    wy1 = 1
    tp = FR % 2
    gbuffer()
    target_rt("scene")
    clear_rt("scene")
    tex_filter(9728)
    set_tex("uPGB", "world", join("gb", 1 - tp))
    tex_filter(9729)
    set_tex("uHist", "world", join("hh", 1 - tp))
    set_vec4("uSSR", "world", 1, 0, 0, 0)
    sky_pass()
    draw_scene(0)
    set_vec4("uSSR", "world", 0, 0, 0, 0)
    vmi = index_of(VMN, api_vm)
    if vmi > 0 and api_cam == 0 and (state == 1 or state == 2):
        draw_device()
    taa()
    post()


@warp
def pick_cam():
    if api_cam == 1:
        cam_free()
    elif api_cam == 2 or api_cam == 3:
        cam_orbit()
    else:
        main_cam()
    api_cyaw_o()


@warp
def api_cyaw_o():
    if api_cam != 1:
        api_cx = round(ccx * 100) / 100
        api_cy = round(ccy * 100) / 100
        api_cz = round(ccz * 100) / 100
        if api_cam == 0:
            api_cyaw = round(yaw * 100) / 100
            api_cpitch = round(pitch * 100) / 100
        else:
            api_cyaw = round(cyaw * 100) / 100
            api_cpitch = round(cpitch * 100) / 100


@warp
def cam_orbit():
    if api_cam == 3:
        cpitch = 0 - api_cpitch
        if api_cyaw != lcyaw:
            cyaw = api_cyaw
    otx = px
    oty = py + 1.4
    otz = pz
    ocp = cos(cpitch)
    obx = 0 - sin(cyaw) * ocp
    oby = sin(cpitch)
    obz = cos(cyaw) * ocp
    if api_cam == 3:
        oby = 0 - oby
    ray_world(otx, oty, otz, obx, oby, obz)
    odist = min(api_cdist, rwt - 0.3)
    odist = max(0.4, odist)
    ccx = otx + obx * odist
    ccy = oty + oby * odist
    ccz = otz + obz * odist
    cfx = 0 - obx
    cfy = 0 - oby
    cfz = 0 - obz
    msy = sin(cyaw)
    mcy = cos(cyaw)
    crx = mcy
    cry = 0
    crz = msy
    cux = cfy * crz - cfz * cry
    cuy = cfz * crx - cfx * crz
    cuz = cfx * cry - cfy * crx
    lcyaw = cyaw


@warp
def ray_world(ox, oy, oz, dx, dy, dz):
    rwt = 999
    rwk = 0
    sk = lh0
    for si in times(lhn):
        sa = HAX[sk]
        if sa == 1:
            sdd = dx
            seo = ox
        elif sa == 2:
            sdd = dy
            seo = oy
        else:
            sdd = dz
            seo = oz
        if sdd * HSG[sk] < -0.0001:
            st_ = (HPL[sk] - seo) / sdd
            if st_ > 0 and st_ < rwt:
                if sa == 1:
                    su = oz + dz * st_
                    sv = oy + dy * st_
                elif sa == 2:
                    su = ox + dx * st_
                    sv = oz + dz * st_
                else:
                    su = ox + dx * st_
                    sv = oy + dy * st_
                if su > HU0[sk] - 0.001 and su < HU1[sk] + 0.001 and sv > HV0[sk] - 0.001 and sv < HV1[sk] + 0.001:
                    rwt = st_
                    rwk = sk
        sk += 1


@warp
def main_cam():
    shy = yaw + shk * shk * (sin(TT * 2900) * 1.4 + sin(TT * 1700) * 0.9)
    shp = pitch + shk * shk * (sin(TT * 2300) * 1.2 + sin(TT * 3700) * 0.7)
    msy = sin(shy)
    mcy = cos(shy)
    msp = sin(shp)
    mcp = cos(shp)
    mbob = min(1, hsp / WALK)
    ccx = px + mcy * sin(bobp * 57.3) * 0.025 * mbob
    ccy = py + eyeh + abs(sin(bobp * 57.3)) * 0.05 * mbob - dip
    ccz = pz + msy * sin(bobp * 57.3) * 0.025 * mbob
    cfx = msy * mcp
    cfy = msp
    cfz = 0 - mcy * mcp
    mrc = cos(roll)
    mrs = sin(roll)
    crx = mcy * mrc + (0 - msy * msp) * mrs
    cry = mcp * mrs
    crz = msy * mrc + mcy * msp * mrs
    cux = (0 - msy * msp) * mrc - mcy * mrs
    cuy = mcp * mrc
    cuz = mcy * msp * mrc - msy * mrs


@warp
def cam_free():
    msy = sin(api_cyaw)
    mcy = cos(api_cyaw)
    msp = sin(api_cpitch)
    mcp = cos(api_cpitch)
    ccx = api_cx
    ccy = api_cy
    ccz = api_cz
    cfx = msy * mcp
    cfy = msp
    cfz = 0 - mcy * mcp
    crx = mcy
    cry = 0
    crz = msy
    cux = 0 - msy * msp
    cuy = mcp
    cuz = mcy * msp


@warp
def gbuffer():
    gbm = 1
    target_rt(join("gb", tp))
    clear_rt(join("gb", tp))
    tex_filter(9728)
    set_tex("uPGB", "world", join("gb", 1 - tp))
    tex_filter(9729)
    set_tex("uHist", "world", join("hh", 1 - tp))
    set_vec4("uGB", "world", 1, 0, 0, 0)
    draw_scene(0)
    if vmi > 0 and api_cam == 0 and (state == 1 or state == 2):
        set_vec4("uGB", "world", 1, 1, 0, 0)
        draw_device()
    set_vec4("uGB", "world", 0, 0, 0, 0)
    gbm = 0


@warp
def sky_pass():
    if LSKY[level] == 1:
        cam_u("sky")
        draw_list("QUAD", "sky")


@warp
def haze_pass():
    target_rt("hz")
    clear_rt("hz")
    tex_filter(9728)
    set_tex("uGBc", "haze", join("gb", tp))
    tex_filter(9729)
    cam_u("haze")
    draw_list("QUAD", "haze")
    blur_pass("hz2", "hz", 2 / RTW, 0)
    blur_pass("hz", "hz2", 0, 2 / RTH)
    blur_pass("hz2", "hz", 4 / RTW, 0)
    blur_pass("hz", "hz2", 0, 4 / RTH)


@warp
def taa():
    haze_pass()
    target_rt(join("hh", tp))
    clear_rt(join("hh", tp))
    set_tex("uCur", "taa", "scene")
    set_tex("uPrev", "taa", join("hh", 1 - tp))
    set_tex("uHz", "taa", "hz")
    tex_filter(9728)
    set_tex("uGBc", "taa", join("gb", tp))
    tex_filter(9729)
    cam_u("taa")
    set_vec2("uTx", "taa", 1 / RTW, 1 / RTH)
    tpd = (ccx - pcx) * (ccx - pcx) + (ccy - pcy) * (ccy - pcy) + (ccz - pcz) * (ccz - pcz)
    if tpd > 2:
        taareset = 1
    set_vec4("uTA", "taa", taareset, 0, 0, 0)
    prev_u("taa")
    draw_list("QUAD", "taa")
    taareset = 0
    pcx = ccx
    pcy = ccy
    pcz = ccz
    prx = crx
    pry = cry
    prz = crz
    pux = cux
    puy = cuy
    puz = cuz
    pfx = cfx
    pfy = cfy
    pfz = cfz
    ppx = PFX
    ppy = PFY
    pjx = jx
    pjy = jy
    jk = FR % 8 + 1
    jx = (JX[jk] - 0.5) * 2 / RTW
    jy = (JY[jk] - 0.5) * 2 / RTH
    prev_u("world")


@warp
def prev_u(sh):
    set_vec3("uPC", sh, pcx, pcy, pcz)
    set_vec3("uPRr", sh, prx, pry, prz)
    set_vec3("uPU", sh, pux, puy, puz)
    set_vec3("uPF", sh, pfx, pfy, pfz)
    set_vec4("uPP", sh, ppx, ppy, pjx, pjy)


@warp
def probe_all():
    envdirty = 0
    target_rt("env")
    clear_rt("env")
    set_tex("uEnv", "world", "atlas")
    set_tex("uEnvB", "world", "atlas")
    set_tex("uEnvC", "world", "atlas")
    set_vec4("uEnvP", "world", 0, 0, 0, 0)
    set_num("uShN", "world", 0)
    PFX = 1
    PFY = 1
    jx = 0
    jy = 0
    set_vec4("uSSR", "world", 0, 0, 0, 0)
    ccx = LPX[level]
    ccy = LPY[level]
    ccz = LPZ[level]
    vpx = 1 / 3
    vpy = 0.5
    for pf in rep(6):
        pfi = (pf - 1) % 3
        pfj = floor((pf - 1) / 3)
        vpox = -1 + (2 * pfi + 1) / 3
        vpoy = -1 + (2 * pfj + 1) / 2
        wx0 = vpox - 1 / 3
        wx1 = vpox + 1 / 3
        wy0 = vpoy - 0.5
        wy1 = vpoy + 0.5
        crx = 0
        cry = 0
        crz = 0
        cux = 0
        cuy = 1
        cuz = 0
        cfx = 0
        cfy = 0
        cfz = 0
        if pf == 1:
            cfx = 1
            crz = 1
        elif pf == 2:
            cfx = -1
            crz = -1
        elif pf == 3:
            cfy = 1
            crx = 1
            cuy = 0
            cuz = -1
        elif pf == 4:
            cfy = -1
            crx = 1
            cuy = 0
            cuz = 1
        elif pf == 5:
            cfz = 1
            crx = -1
        else:
            cfz = -1
            crx = 1
        sky_pass()
        cam_u("world")
        model_id()
        set_vec4("uMode", "world", 0, 1, 0, 0)
        draw_geo(GIDW[level])
    vpx = 1
    vpy = 1
    vpox = 0
    vpoy = 0
    env_blur("enve", "env", 1.5 / (3 * ENVT), 0)
    env_blur("envb", "enve", 0, 1.5 / (2 * ENVT))
    env_blur("envd", "envb", 3 / (3 * ENVT), 0)
    env_blur("envc", "envd", 0, 3 / (2 * ENVT))
    env_blur("envd", "envc", 5 / (3 * ENVT), 0)
    env_blur("envc", "envd", 0, 5 / (2 * ENVT))
    target_rt("scene")
    set_tex("uEnv", "world", "env")
    set_tex("uEnvB", "world", "envb")
    set_tex("uEnvC", "world", "envc")
    set_vec4("uEnvP", "world", LPX[level], LPY[level], LPZ[level], 1)
    set_vec3("uBox0", "world", LB0X[level], LB0Y[level], LB0Z[level])
    set_vec3("uBox1", "world", LB1X[level], LB1Y[level], LB1Z[level])
    wx0 = -1
    wy0 = -1
    wx1 = 1
    wy1 = 1


@warp
def env_blur(dst, src, dx, dy):
    target_rt(dst)
    clear_rt(dst)
    set_tex("uSrc", "eblur", src)
    set_vec2("uDir", "eblur", dx, dy)
    draw_list("QUAD", "eblur")


@warp
def frame_uniforms():
    PFY = 1 / tan((api_fov + fovk) / 2)
    PFX = PFY * 9 / 16
    set_vec4("uO1", "world", px, py + 0.45, pz, 0.36)
    set_vec4("uO2", "world", px, py + 1.15, pz, 0.34)
    shadows_pick()


@warp
def shadows_pick():
    for sci in rep(NSHAD):
        KCOL[sci] = 0
    shn = 0
    for sci in rep(NSHAD):
        sbd = 9999
        sbk = 0
        for sck in rep(nobj):
            sod = LO0[level] + sck - 1
            if DSHAD[sod] == 1 and obj_visible[sck] == 1:
                sdd2 = ((OAX0[sck] + OAX1[sck]) / 2 - ccx) * ((OAX0[sck] + OAX1[sck]) / 2 - ccx) + ((OAZ0[sck] + OAZ1[sck]) / 2 - ccz) * ((OAZ0[sck] + OAZ1[sck]) / 2 - ccz)
                if sdd2 < sbd and not (sck == KCOL[1] or sck == KCOL[2] or sck == KCOL[3] or sck == KCOL[4]):
                    sbd = sdd2
                    sbk = sck
        if sbk > 0:
            shn += 1
            KCOL[shn] = sbk
            sod = LO0[level] + sbk - 1
            obj_basis(sbk)
            sox_ = DBCX[sod] * osx_
            soy_ = DBCY[sod] * osy2
            soz_ = DBCZ[sod] * osz_
            scx = obj_x[sbk] + bxx * sox_ + byx * soy_ + bzx * soz_
            scy = obj_y[sbk] + bxy * sox_ + byy * soy_ + bzy * soz_ + OOPN[sbk] * DSLIDE[sod]
            scz = obj_z[sbk] + bxz * sox_ + byz * soy_ + bzz * soz_
            set_arr4(shn, "uSC", "world", scx, scy, scz, DBZ[sod] * osz_)
            set_arr4(shn, "uSX", "world", bxx, bxy, bxz, DBX[sod] * osx_)
            set_arr4(shn, "uSY", "world", byx, byy, byz, DBY[sod] * osy2)
    set_num("uShN", "world", shn)


@warp
def cam_u(sh):
    set_vec3("uCP", sh, ccx, ccy, ccz)
    set_vec3("uCR", sh, crx, cry, crz)
    set_vec3("uCU", sh, cux, cuy, cuz)
    set_vec3("uCF", sh, cfx, cfy, cfz)
    set_vec4("uProj", sh, PFX, PFY, NEAR, FAR)
    set_vec4("uWin", sh, wx0, wy0, wx1, wy1)
    set_vec4("uVP", sh, vpx, vpy, vpox, vpoy)
    set_vec2("uJit", sh, jx, jy)


@warp
def model_id():
    set_vec3("uMP", "world", 0, 0, 0)
    set_vec3("uMX", "world", 1, 0, 0)
    set_vec3("uMY", "world", 0, 1, 0)
    set_vec3("uMZ", "world", 0, 0, 1)


@warp
def amb_at(x, y, z):
    ast_ = AMBST[level]
    aix = max(0, min(AMBNX[level] - 1, floor((x - AMBOX[level]) / ast_ + 0.5)))
    aiy = max(0, min(AMBNY[level] - 1, floor((y - AMBOY[level]) / ast_ + 0.5)))
    aiz = max(0, min(AMBNZ[level] - 1, floor((z - AMBOZ[level]) / ast_ + 0.5)))
    ak = AMB0[level] + ((aix * AMBNY[level] + aiy) * AMBNZ[level] + aiz) * 6
    amb_dir("uA0", AMB[ak])
    amb_dir("uA1", AMB[ak + 1])
    amb_dir("uA2", AMB[ak + 2])
    amb_dir("uA3", AMB[ak + 3])
    amb_dir("uA4", AMB[ak + 4])
    amb_dir("uA5", AMB[ak + 5])


@warp
def amb_dir(name, v):
    adr = floor(v / 1000000)
    adg = floor((v - adr * 1000000) / 1000)
    adb = v - adr * 1000000 - adg * 1000
    set_vec3(name, "world", adr * AMBS, adg * AMBS, adb * AMBS)


@warp
def draw_scene(vq):
    cam_u("world")
    cam_u("part")
    model_id()
    set_vec4("uMode", "world", 0, 1, 0, 0)
    draw_geo(GIDW[level])
    for dk in rep(nobj):
        if obj_visible[dk] == 1:
            draw_obj(dk)
    set_vec4("uMode", "world", 1, 1, 0, 0)
    if api_cam != 0:
        draw_player()
    if gbm == 0:
        set_vec4("uPM", "part", 0, LFY[level], LCY_[level], 0)
        set_vec3("uCol", "part", 1.0, 0.95, 0.85)
        draw_list("DUST", "part")
        vj = LV0[level]
        for vji in times(LVNN[level]):
            set_vec3("uQC", "part", (VX0[vj] + VX1[vj]) / 2, VY0[vj], (VZ0[vj] + VZ1[vj]) / 2)
            set_vec3("uQR", "part", (VX1[vj] - VX0[vj]) / 2, 0, (VZ1[vj] - VZ0[vj]) / 2)
            set_vec4("uPM", "part", 4, VY1[vj] - VY0[vj], 1.0, 0)
            set_vec3("uCol", "part", 0.75, 0.9, 1.1)
            draw_list("VENTP", "part")
            vj += 1
        sj = LSP0[level]
        for sji in times(LSPN[level]):
            spt = (TT * 0.9 + sji * 0.37) % 1.6
            if spt < 0.7:
                set_vec3("uQC", "part", SPX[sj], SPY[sj], SPZ[sj])
                set_vec3("uQN", "part", 0, -1, 0)
                set_vec4("uPM", "part", 3, spt, 0.9, 0)
                set_vec3("uCol", "part", 3.0, 2.2, 1.2)
                draw_list("IMPACT", "part")
            sj += 1


@warp
def draw_obj(k):
    od = LO0[level] + k - 1
    obj_basis(k)
    amb_at((OAX0[k] + OAX1[k]) / 2, (OAY0[k] + OAY1[k]) / 2, (OAZ0[k] + OAZ1[k]) / 2)
    og_ = obj_glow[k]
    if DKIND[od] == 2:
        og_ = og_ * (1 + OOPN[k] * 2)
    set_vec3("uEmit", "world", DGR[od] * og_, DGG[od] * og_, DGB[od] * og_)
    set_vec3("uMP", "world", obj_x[k], obj_y[k] + OOPN[k] * DSLIDE[od], obj_z[k])
    set_vec3("uMX", "world", bxx * osx_, bxy * osx_, bxz * osx_)
    set_vec3("uMY", "world", byx * osy2, byy * osy2, byz * osy2)
    set_vec3("uMZ", "world", bzx * osz_, bzy * osz_, bzz * osz_)
    if DPRS[od] > 0:
        set_vec4("uMode", "world", 1, 1, 0, 1)
        set_vec4("uPR", "world", DPRX[od], DPRY[od], DPRS[od], DPRT[od])
    else:
        set_vec4("uMode", "world", 1, 1, 0, 0)
    draw_geo(DG[od])
    if DG2[od] > 0:
        set_vec3("uMP", "world", obj_x[k], obj_y[k] + 0.06 - OOPN[k] * 0.05, obj_z[k])
        set_vec4("uPR", "world", DPRX2[od], DPRY2[od], DPRS2[od], DPRT2[od])
        draw_geo(DG2[od])


@warp
def draw_player():
    amb_at(px, py + 1, pz)
    set_vec3("uEmit", "world", 0.3, 0.6, 1.0)
    set_vec3("uMP", "world", px, py, pz)
    set_vec3("uMX", "world", cos(yaw), 0, sin(yaw))
    set_vec3("uMY", "world", 0, 1, 0)
    set_vec3("uMZ", "world", 0 - sin(yaw), 0, cos(yaw))
    set_vec4("uMode", "world", 1, 1, 0, 1)
    set_vec4("uPR", "world", PR_PLAYER_X, PR_PLAYER_Y, PR_PLAYER_S, PR_PLAYER_T)
    pose()
    draw_geo(G_PLAYER)
    set_vec4("uSkin", "world", 0, 0, 0, 0)
    set_vec4("uMode", "world", 1, 1, 0, 0)


@warp
def pose():
    wa = min(1, hsp / 6) * (1 - airk)
    sp = sin(bobp * 57.3)
    cp = cos(bobp * 57.3)
    lth = wa * 0.5 * sp + airk * 0.55 + crk * 1.1
    rth = 0 - wa * 0.5 * sp - airk * 0.2 + crk * 1.1
    lkn = 0 - wa * (0.12 + 0.95 * max(0, cp)) - airk * 1.0 - crk * 1.9
    rkn = 0 - wa * (0.12 + 0.95 * max(0, 0 - cp)) - airk * 0.55 - crk * 1.9
    lua = 0 - wa * 0.38 * sp + airk * 0.5
    lfa = 0.18 + wa * 0.35 + airk * 0.5
    rua = wa * 0.1 * sp - airk * 0.15
    rfa = 0 - airk * 0.1
    prd = max(-70, min(70, pitch)) * 0.01745
    idb = (1 - wa) * (1 - airk)
    brt = sin(TT * 95)
    dpk = min(1, dip * 5)
    lth += dpk * 0.55
    rth += dpk * 0.55
    lkn += 0 - dpk * 1.0
    rkn += 0 - dpk * 1.0
    lua += prd * 0.35 + brt * 0.02 * idb
    rua += prd * 0.55 - brt * 0.02 * idb
    rfa += prd * 0.25
    spn = 0 - wa * 0.12 - crk * 0.35 - airk * 0.08 + prd * 0.18 + brt * 0.015 * idb - dpk * 0.18
    bob = 0 - wa * 0.035 * abs(sp) - crk * 0.42 + brt * 0.006 * idb - dpk * 0.16
    set_vec4("uSkin", "world", 1, bob, 0, 0)
    set_vec4("uSk0", "world", lth, lkn, rth, rkn)
    set_vec4("uSk1", "world", lua, lfa, rua, rfa)
    set_vec4("uSk2", "world", 0 - spn * 0.6 + prd * 0.5, spn, 0, 0)


@warp
def draw_geo(gi):
    tex_filter(9728)
    set_tex("uGeo", "world", GTEX[gi])
    tex_filter(9729)
    set_vec4("uGeoP", "world", GOX[gi], GOY[gi], GOZ[gi], GR[gi])
    if GNC[gi] == 0:
        set_vec4("uGeoI", "world", GB[gi], GC[gi], GH[gi], GIB[gi])
        draw_list("ICS", "world")
    else:
        gco = 0
        for gk in rep(GNC[gi]):
            set_vec4("uGeoI", "world", GB[gi] + gco, min(49152, GC[gi] - gco), GH[gi], GIB[gi])
            draw_list("IC", "world")
            gco += 49152


@warp
def draw_device():
    vraise = max(0, vraise - dt * 1.6)
    holdk += (lheld - holdk) * min(1, dt * 8)
    dbob = min(1, hsp / WALK)
    idl = 1 - dbob
    dsx = sin(bobp * 57.3) * 0.008 * dbob + vmswx + sin(TT * 75) * 0.0022 * idl + sin(TT * 1400) * 0.0006 * holdk
    dsy = abs(sin(bobp * 57.3)) * 0.007 * dbob + vmswy - dip * 0.12 - vk * 0.012 - vraise * vraise * 0.3 - holdk * 0.025
    dsy += sin(TT * 126) * 0.0016 * idl + sin(TT * 1900) * 0.0005 * holdk - airk * 0.008
    dsz = 0 - vk * 0.055 + grk * 0.045
    dox = ccx + crx * (0.165 + dsx) + cux * (-0.145 + dsy) + cfx * (0.4 + dsz)
    doy = ccy + cry * (0.165 + dsx) + cuy * (-0.145 + dsy) + cfy * (0.4 + dsz)
    doz = ccz + crz * (0.165 + dsx) + cuz * (-0.145 + dsy) + cfz * (0.4 + dsz)
    dya = 5 + vk * 3 + sin(TT * 60) * 0.5 * idl
    dpa = 4 - vk * 11 + vraise * vraise * 35 - holdk * 6 - grk * 9 - dip * 40 + airk * 3
    dca = cos(dya)
    dsa = sin(dya)
    dcb = cos(dpa)
    dsb = sin(dpa)
    dzx = (cfx * dca - crx * dsa) * dcb + cux * dsb
    dzy = (cfy * dca - cry * dsa) * dcb + cuy * dsb
    dzz = (cfz * dca - crz * dsa) * dcb + cuz * dsb
    dxx = crx * dca + cfx * dsa
    dxy = cry * dca + cfy * dsa
    dxz = crz * dca + cfz * dsa
    dyx = dzy * dxz - dzz * dxy
    dyy = dzz * dxx - dzx * dxz
    dyz = dzx * dxy - dzy * dxx
    dra = vroll * 2.2 + vk * 5 + sin(TT * 45) * 0.6 * idl
    drc = cos(dra)
    drs = sin(dra)
    rxx = dxx * drc - dyx * drs
    rxy = dxy * drc - dyy * drs
    rxz = dxz * drc - dyz * drs
    dyx = dyx * drc + dxx * drs
    dyy = dyy * drc + dxy * drs
    dyz = dyz * drc + dxz * drs
    dxx = rxx
    dxy = rxy
    dxz = rxz
    amb_at(px, py + eyeh, pz)
    set_vec3("uEmit", "world", VMR[vmi] * 2.2, VMGC[vmi] * 2.2, VMB[vmi] * 2.2)
    set_vec4("uWin", "world", -1, -1, 1, 1)
    vms = VMS[vmi]
    set_vec3("uMP", "world", dox + dxx * VMOX[vmi] - dyx * VMOY[vmi] + dzx * VMOZ[vmi], doy + dxy * VMOX[vmi] - dyy * VMOY[vmi] + dzy * VMOZ[vmi], doz + dxz * VMOX[vmi] - dyz * VMOY[vmi] + dzz * VMOZ[vmi])
    set_vec3("uMX", "world", dxx * vms, dxy * vms, dxz * vms)
    set_vec3("uMY", "world", (0 - dyx) * vms, (0 - dyy) * vms, (0 - dyz) * vms)
    set_vec3("uMZ", "world", dzx * vms, dzy * vms, dzz * vms)
    if VMG[vmi] > 0:
        if VMPRS[vmi] > 0:
            set_vec4("uMode", "world", 1, 1, 1, 1)
            set_vec4("uPR", "world", VMPRX[vmi], VMPRY[vmi], VMPRS[vmi], VMPRT[vmi])
        else:
            set_vec4("uMode", "world", 1, 1, 1, 0)
        draw_geo(VMG[vmi])
    if VMARM[vmi] == 1:
        set_vec3("uMP", "world", dox, doy, doz)
        set_vec3("uMX", "world", dxx, dxy, dxz)
        set_vec3("uMY", "world", 0 - dyx, 0 - dyy, 0 - dyz)
        set_vec3("uMZ", "world", dzx, dzy, dzz)
        set_vec4("uMode", "world", 1, 1, 1, 1)
        set_vec4("uPR", "world", PR_ARMS_X, PR_ARMS_Y, PR_ARMS_S, PR_ARMS_T)
        draw_geo(G_ARMS)


@warp
def post():
    target_rt("b1")
    clear_rt("b1")
    set_tex("uSrc", "bright", join("hh", tp))
    set_vec2("uTx", "bright", 1 / RTW, 1 / RTH)
    set_vec4("uBP", "bright", 0.85, 0.9, 0, 0)
    draw_list("QUAD", "bright")
    blur_pass("b2", "b1", 4 / RTW, 0)
    blur_pass("b1", "b2", 0, 4 / RTH)
    blur_pass("b3", "b1", 4 / RTW, 0)
    blur_pass("b4", "b3", 0, 8 / RTH)
    blur_pass("b3", "b4", 8 / RTW, 0)
    target_rt("Scratch Stage")
    pen_clear()
    clear_depth()
    set_tex("uScene", "comp", join("hh", tp))
    set_tex("uB1", "comp", "b1")
    set_tex("uB2", "comp", "b3")
    set_vec2("uTx", "comp", 1 / RTW, 1 / RTH)
    set_vec4("uPost", "comp", EXPO * LEXP[level] * api_expo, 0.55, 0.45, 0.55)
    set_vec4("uFx", "comp", max(tfade, api_fade), 0, 0.45, 0)
    set_vec3("uFlash", "comp", api_flash, api_flash, api_flash)
    draw_list("QUAD", "comp")
    api_flash = max(0, api_flash - dt * 2)


@warp
def blur_pass(dst, src, dx, dy):
    target_rt(dst)
    clear_rt(dst)
    set_tex("uSrc", "blur", src)
    set_vec2("uDir", "blur", dx, dy)
    draw_list("QUAD", "blur")
