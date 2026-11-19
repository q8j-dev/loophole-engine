@when_flag
def audio_start():
    for audio_i in range(len(ATYPES)):
        my_sound = ATYPES[audio_i + 1]
        clone()


@when_clone
def audio_loop():
    if my_sound == "engine":
        while True:
            play("amb_engine")
            wait(1.97)
            play("amb_engine_b")
            wait(1.97)
    while True:
        play(join("amb_", my_sound))
        wait(12)
        play(join(join("amb_", my_sound), "_b"))
        wait(12)


@when_clone
def audio_mix():
    if my_sound == "engine":
        while True:
            if driving == "":
                set_volume(0)
            else:
                set_volume((0.45 + 0.55 * engine_rpm) * 55 * (1 - fade))
            set_pitch(engine_rpm * 110 - 25)
            wait(0)
    while True:
        gain = 0
        pan = 0
        first = AL0[level]
        for audio_j in range(ALN[level]):
            e = first + audio_j
            if ASN[e] == my_sound:
                if AK[e] == 0:
                    sx = AX[e]
                    sy = AY[e]
                    sz = AZ[e]
                    if AOB[e] != "":
                        on = index_of(obj_name, AOB[e])
                        if on > 0:
                            sx = obj_x[on]
                            sy = obj_y[on]
                            sz = obj_z[on]
                    dx = sx - camera_x
                    dz = sz - camera_z
                    dist = sqrt(dx * dx + (sy - camera_y) * (sy - camera_y) + dz * dz)
                    g = 1 - (dist - ANR[e]) / (AFR[e] - ANR[e])
                    spread = dist / (ANR[e] + 1)
                else:
                    nx = camera_x
                    if nx < AX[e]:
                        nx = AX[e]
                    if nx > AX1[e]:
                        nx = AX1[e]
                    nz = camera_z
                    if nz < AZ[e]:
                        nz = AZ[e]
                    if nz > AZ1[e]:
                        nz = AZ1[e]
                    dx = nx - camera_x
                    dz = nz - camera_z
                    dist = sqrt(dx * dx + dz * dz)
                    g = 1 - dist / AFR[e]
                    spread = dist / 4
                if g > 1:
                    g = 1
                if g > 0:
                    g = g * g * AV[e]
                    if g > gain:
                        gain = g
                        pan = 0
                        if dist > 0.05:
                            if spread > 1:
                                spread = 1
                            pan = (dx * cos(camera_yaw) + dz * sin(camera_yaw)) / dist * 90 * spread
        set_volume(gain * 100 * (1 - fade))
        set_pan(pan)
        wait(0)
