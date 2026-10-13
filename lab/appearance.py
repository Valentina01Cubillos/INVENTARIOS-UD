def rgb(value):
    return tuple(int(value[i:i+2],16) for i in (1,3,5))

def mix(value,target,amount):
    return '#'+''.join(f'{round(a*(1-amount)+b*amount):02x}' for a,b in zip(rgb(value),rgb(target)))

def foreground(value):
    channels=[c/255 for c in rgb(value)]
    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
    luminance=sum(c*w for c,w in zip(linear,(.2126,.7152,.0722)))
    return '#17252c' if luminance>.179 else '#ffffff'

def theme(preferences):
    primary=preferences.primario
    secondary=preferences.secundario
    sidebar=mix(primary,'#000000',.18)
    return {'primary':primary,'primary_text':foreground(primary),
        'primary_soft':mix(primary,'#ffffff',.93),'primary_ink':mix(primary,'#17252c',.4),
        'primary_hover':mix(primary,'#000000',.08),'sidebar':sidebar,'sidebar_text':foreground(sidebar),
        'secondary':secondary,'secondary_text':foreground(secondary),
        'secondary_soft':mix(secondary,'#ffffff',.65),'secondary_ink':mix(secondary,'#17252c',.6),
        'background':preferences.fondo,'background_text':foreground(preferences.fondo)}
