"""Small interactive editor for an irregular four-or-more-wall room plan."""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons

from .room import validate_polygon


LAYOUT_CHOICES = ("5.1", "5.2", "7.1", "7.2", "5.1.2", "5.1.4",
                  "7.1.2", "7.1.4", "7.2.4", "9.1.6", "custom")


def _cross(a, b, c):
    return float(np.cross(b-a, c-a))


def _segments_intersect(a, b, c, d):
    eps=1e-9
    o1,o2,o3,o4=_cross(a,b,c),_cross(a,b,d),_cross(c,d,a),_cross(c,d,b)
    if o1*o2 < -eps and o3*o4 < -eps: return True
    def on_segment(p,q,r):
        return min(p[0],r[0])-eps<=q[0]<=max(p[0],r[0])+eps and min(p[1],r[1])-eps<=q[1]<=max(p[1],r[1])+eps
    return ((abs(o1)<=eps and on_segment(a,c,b)) or (abs(o2)<=eps and on_segment(a,d,b)) or
            (abs(o3)<=eps and on_segment(c,a,d)) or (abs(o4)<=eps and on_segment(c,b,d)))


def _valid_simple(points):
    try: p=validate_polygon(np.asarray(points,dtype=float).T)
    except ValueError: return False
    n=p.shape[1]
    for i in range(n):
        for j in range(i+1,n):
            if j in (i,(i+1)%n) or i==(j+1)%n: continue
            if _segments_intersect(p[:,i],p[:,(i+1)%n],p[:,j],p[:,(j+1)%n]): return False
    return True


def edit_room(room_polygon_m, selected_layout="5.1", validator=None, initial_message=None):
    """Let the user drag vertices, add/remove corners, and choose a layout.

    Double-click an edge to insert a vertex. A validator can keep the editor
    open with a specific explanation when a room cannot host the selected layout.
    Returns ``(2xN polygon metres, layout name)`` when Optimize is pressed.
    """
    original=np.asarray(room_polygon_m,dtype=float).T.copy()
    points=[point.copy() for point in original]
    accepted={"room":None,"layout":selected_layout if selected_layout in LAYOUT_CHOICES else "5.1"}
    fig,ax=plt.subplots(figsize=(10,7)); fig.subplots_adjust(right=.76,bottom=.17)
    ax.set_title("Drag room corners · double-click a wall to add a point")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_aspect("equal",adjustable="box")
    span=max(float(np.ptp(original[:,0])),float(np.ptp(original[:,1])),1.)
    ax.set_xlim(float(original[:,0].min())-.15*span,float(original[:,0].max())+.15*span)
    ax.set_ylim(float(original[:,1].min())-.15*span,float(original[:,1].max())+.15*span)
    line,=ax.plot([],[],"-",color="#276678",lw=2,marker="o",markersize=9,
                  markerfacecolor="#f2a365",markeredgecolor="#17424d",picker=8)
    labels=[]
    status=ax.text(.02,.98,initial_message or "Move a point and release to reshape the room.",transform=ax.transAxes,va="top")
    status.set_wrap(True); status.set_fontsize(8)
    layout_ax=fig.add_axes([.79,.24,.19,.65])
    choices=list(LAYOUT_CHOICES)
    radios=RadioButtons(layout_ax,choices,active=choices.index(accepted["layout"]))
    layout_ax.set_title("Theatre format",fontsize=10)
    dragging={"index":None,"last":None}
    controls=[]

    def redraw():
        closed=points+[points[0]]
        line.set_data([p[0] for p in closed],[p[1] for p in closed])
        for label in labels: label.remove()
        labels.clear()
        for i,p in enumerate(points): labels.append(ax.text(p[0],p[1],str(i+1),fontsize=8,ha="center",va="center"))
        fig.canvas.draw_idle()

    def optimize(_event):
        if not _valid_simple(points): status.set_text("Room boundary is invalid; correct it before optimizing."); fig.canvas.draw_idle(); return
        if validator is not None:
            try: validator(np.asarray(points,dtype=float).T.copy(),accepted["layout"])
            except ValueError as exc:
                message=str(exc); print("Room/layout not feasible yet:",message,flush=True)
                status.set_text("Layout needs adjustment:\n{}\nEdit the room or choose another format, then press Optimize again.".format(message))
                fig.canvas.draw_idle(); return
        accepted["room"]=np.asarray(points,dtype=float).T.copy(); plt.close(fig)

    def add_point(_event):
        n=len(points); lengths=[np.linalg.norm(points[(i+1)%n]-points[i]) for i in range(n)]
        i=int(np.argmax(lengths)); points.insert(i+1,(points[i]+points[(i+1)%n])/2.)
        redraw()

    def remove_point(_event):
        if len(points)<=3: status.set_text("A room needs at least three corners."); fig.canvas.draw_idle(); return
        points.pop(); redraw()

    def press(event):
        if event.inaxes is not ax or event.xdata is None: return
        if event.dblclick:
            p=np.array([event.xdata,event.ydata]); n=len(points)
            nearest=min(range(n),key=lambda i:np.linalg.norm(p-points[i]))
            nxt=(nearest+1)%n; edge=points[nxt]-points[nearest]
            t=np.clip(float((p-points[nearest])@edge/max(edge@edge,1e-12)),.05,.95)
            points.insert(nxt,points[nearest]+t*edge); redraw(); return
        mouse=np.array([event.xdata,event.ydata]); mouse_px=ax.transData.transform(mouse)
        nearest=min(range(len(points)),key=lambda i:np.linalg.norm(ax.transData.transform(points[i])-mouse_px))
        if np.linalg.norm(ax.transData.transform(points[nearest])-mouse_px) < 16.:
            dragging["index"]=nearest; dragging["last"]=points[nearest].copy()

    def motion(event):
        i=dragging["index"]
        if i is None or event.inaxes is not ax or event.xdata is None: return
        points[i]=np.array([event.xdata,event.ydata]); redraw()

    def release(_event):
        i=dragging["index"]
        if i is None: return
        if not _valid_simple(points):
            points[i]=dragging["last"]; status.set_text("That move would make the room boundary invalid; point restored.")
        dragging["index"]=None; dragging["last"]=None; redraw()

    radios.on_clicked(lambda value: accepted.update(layout=value))
    fig.canvas.mpl_connect("button_press_event",press); fig.canvas.mpl_connect("motion_notify_event",motion)
    fig.canvas.mpl_connect("button_release_event",release)
    controls.append(Button(fig.add_axes([.79,.13,.09,.055]),"Add corner")); controls[-1].on_clicked(add_point)
    controls.append(Button(fig.add_axes([.89,.13,.09,.055]),"Remove last")); controls[-1].on_clicked(remove_point)
    controls.append(Button(fig.add_axes([.79,.055,.19,.06]),"Optimize")); controls[-1].on_clicked(optimize)
    redraw(); plt.show()
    if accepted["room"] is None: raise ValueError("room design was closed without pressing Optimize")
    return accepted["room"],accepted["layout"]
