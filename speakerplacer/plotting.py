"""Type-aware matplotlib candidate, placement, and response figures."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from .room import meters_to_ft
from .scoring import direct_arrival

_TYPE_COLORS={"front":"orangered","surround":"royalblue","bass":"darkviolet"}
_TYPE_MARKERS={"front":"o","surround":"s","bass":"D"}

def _base(ax,result,title,legend=False):
    p=result.room_polygon_m; q=np.column_stack([p,p[:,0]])/0.3048
    ax.plot(q[0],q[1],color="black",lw=1.5)
    listener=result.listener_m/0.3048
    ax.plot(listener[0],listener[1],marker="*",ms=13,color="gold",mec="black",label="Listener",zorder=5)
    direction={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[result.facing]
    ax.annotate("",xy=listener+direction*.8/0.3048,xytext=listener,arrowprops=dict(arrowstyle="->",lw=1.6,color="black"))
    ax.set_aspect("equal",adjustable="box"); ax.set_xlabel("x (ft)"); ax.set_ylabel("y (ft)"); ax.set_title(title)
    lo=q.min(axis=1); hi=q.max(axis=1); span=hi-lo; ax.set_xlim(lo[0]-.04*span[0]-.25,hi[0]+.04*span[0]+.25); ax.set_ylim(lo[1]-.04*span[1]-.25,hi[1]+.04*span[1]+.25)

def _draw_wedge(ax,result,placement):
    spec=placement.get("spec",{}); target=spec.get("angle_target_deg")
    if target is None:return
    tol=spec.get("angle_tol_deg",0.); forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[result.facing]; right=np.array([forward[1],-forward[0]])
    radius=2.5*float(np.linalg.norm(result.room_polygon_m.max(axis=1)-result.room_polygon_m.min(axis=1)))
    angles=[]
    if target<90: angles=[(-target-tol,-target+tol),(target-tol,target+tol)]
    else: angles=[(-target-tol,-target+tol),(target-tol,target+tol)]
    origin=result.listener_m
    for lo,hi in angles:
        theta=np.radians(np.linspace(lo,hi,25)); arc=[origin+radius*(np.sin(a)*right+np.cos(a)*forward) for a in theta]
        vertices=np.vstack([origin,arc])/0.3048; ax.add_patch(Polygon(vertices,closed=True,facecolor="gray",alpha=.08,edgecolor="none"))

def add_speaker_label(ax, speaker, position_ft, index, include_coordinates=True):
    """Attach a type-and-coordinate label to its own plotted speaker point."""
    normal=np.asarray(speaker.get("normal",np.array([0.,-1.])),dtype=float)
    if abs(normal[0])>abs(normal[1]):
        dx=15 if normal[0]>0 else -15; dy=8+(index%3)*8; ha="left" if dx>0 else "right"; va="center"
    else:
        dx=8 if index%2 else -8; dy=15 if normal[1]>0 else -15; ha="left" if dx>0 else "right"; va="bottom" if dy>0 else "top"
    label="{}: {}".format(speaker["type"],speaker.get("model_id","model"))
    if include_coordinates: label+=" ({:.2f}, {:.2f} ft)".format(*position_ft)
    return ax.annotate(label,xy=position_ft,xytext=(dx,dy),textcoords="offset points",ha=ha,va=va,fontsize=7.5,clip_on=False,bbox={"facecolor":"white","edgecolor":"none","alpha":.8,"pad":1.2})

def plot_results(result,output_dir="output",show=True):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); figs=[]
    placement_types=result.placements_by_type or [{"type":"speaker","best":result.best_pair,"ranked":[result.best_pair],"spec":{}}]
    fig,axes=plt.subplots(1,len(placement_types),figsize=(6*len(placement_types),5),squeeze=False)
    for ax,placement in zip(axes[0],placement_types):
        name=placement["type"]; channel=placement.get("channel")
        title="Candidate positions: {}".format(channel if channel else name)
        _base(ax,result,title); _draw_wedge(ax,result,placement)
        rows=[row for row in result.candidate_scores if row["type"]==name and (channel is None or row.get("channel")==channel)]
        if rows:
            coords=np.array([row["position_m"] for row in rows])/0.3048; vals=np.array([row["score_db"] for row in rows])
            sc=ax.scatter(coords[:,0],coords[:,1],c=vals,cmap="viridis",s=24); cb=fig.colorbar(sc,ax=ax,fraction=.046,pad=.04); cb.set_label("Score (dB), higher is better")
    fig.tight_layout(); fig.savefig(out/"candidate_speakers.png",dpi=180); figs.append(fig)

    fig2,ax2=plt.subplots(figsize=(9,6)); _base(ax2,result,"Recommended speaker placement")
    speakers=result.best_pair.get("speakers",[]); listener=result.listener_m/0.3048
    if len(speakers)>=2:
        forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[result.facing]; right=np.array([forward[1],-forward[0]])
        local_angles=[np.arctan2(np.dot(s["position_m"]-result.listener_m,right),np.dot(s["position_m"]-result.listener_m,forward)) for s in speakers]
        ordered=np.array([speakers[i]["position_m"]/0.3048 for i in np.argsort(local_angles)])
        ax2.add_patch(Polygon(np.vstack([ordered,listener]),closed=True,facecolor="orange",alpha=.1,edgecolor="none"))
    markers={}; handles={}
    for i,speaker in enumerate(speakers):
        name=speaker["type"]; color=_TYPE_COLORS.get(name,plt.get_cmap("tab10")(i%10)); marker=_TYPE_MARKERS.get(name,"o")
        pt=speaker["position_m"]/0.3048; normal=speaker.get("normal",np.array([0.,-1.])); wall=speaker["wall_index"]
        ax2.plot([pt[0],listener[0]],[pt[1],listener[1]],"--",color=color,alpha=.55,lw=1)
        artist=ax2.scatter(*pt,s=115,c=[color],marker=marker,edgecolors="black",label=name,zorder=4)
        if name not in handles: handles[name]=artist
        aim=np.asarray(speaker.get("aim_direction",normal),dtype=float); ax2.annotate("",xy=pt+.5*aim/0.3048,xytext=pt,arrowprops=dict(arrowstyle="->",color="black",lw=1))
        coverage=float(speaker.get("coverage_h_deg",360.))
        if coverage<359.:
            theta=np.arctan2(aim[1],aim[0]); angles=np.linspace(theta-np.radians(coverage/2),theta+np.radians(coverage/2),31)
            radius=float(np.linalg.norm(result.listener_m-speaker["position_m"]))/0.3048
            arc=pt+radius*np.column_stack([np.cos(angles),np.sin(angles)])
            ax2.add_patch(Polygon(np.vstack([pt,arc]),closed=True,facecolor=color,alpha=.09,edgecolor="none",zorder=1))
        to_listener=result.listener_m-speaker["position_m"]; cosine=np.dot(normal,to_listener)/(max(np.linalg.norm(normal)*np.linalg.norm(to_listener),1e-12)); offaxis=np.degrees(np.arccos(np.clip(cosine,-1,1)))
        if offaxis>coverage/2 and name!="bass": result.warnings.append("WARN: listener is outside the {} coverage cone ({:.1f} deg vs {:.1f} deg half-coverage)".format(name,offaxis,coverage/2))
        short_label=speaker["type"]
        normal2=np.asarray(speaker.get("normal",[0.,-1.]))
        dx=12 if normal2[0]>=0 else -12
        dy=-16-(i%2)*10 if normal2[1]<-.5 else (16+(i%2)*10 if normal2[1]>.5 else (12 if i%2 else -12))
        ax2.annotate(short_label,xy=pt,xytext=(dx,dy),textcoords="offset points",ha="left" if dx>0 else "right",va="top" if dy<0 else "bottom",fontsize=8,clip_on=False,bbox={"facecolor":"white","edgecolor":"none","alpha":.9,"pad":1.2})
    for placement in placement_types:
        for ranked in placement.get("ranked",[])[1:]:
            for speaker in ranked.get("speakers",[]):
                pt=speaker["position_m"]/0.3048; ax2.scatter(*pt,s=28,c="gray",alpha=.3,marker=".")
    # Save a separate wrapped table so model names and warnings remain readable.
    coord_rows=[]
    for s in speakers:
        position=np.asarray(s["position_m"])/.3048
        import textwrap
        coord_rows.append([s["type"],s.get("model_id","model"),"{:.2f}".format(position[0]),"{:.2f}".format(position[1]),"{:+.0f}°".format(s.get("toe_in_deg",0.)),"{:.1f}".format(s.get("predicted_spl_db",float("nan"))),"{:+.1f}".format(s.get("headroom_db",float("nan"))),textwrap.fill("; ".join(s.get("warnings",[])) or "—",width=38)])
    if coord_rows:
        table_fig,table_ax=plt.subplots(figsize=(13,max(2.2,1.2+.52*len(coord_rows))))
        table_ax.axis("off")
        table=table_ax.table(cellText=coord_rows,colLabels=["Role","Model","x (ft)","y (ft)","Yaw","SPL","Headroom","Warnings"],loc="center",cellLoc="left",colWidths=[.09,.28,.08,.08,.07,.08,.1,.35])
        table.auto_set_font_size(False); table.set_fontsize(8); table.scale(1.,1.5)
        for (row_index,_),cell in table.get_celld().items():
            if row_index==0: cell.set_text_props(weight="bold")
            cell.get_text().set_wrap(True)
        table_fig.tight_layout(); table_fig.savefig(out/"speaker_table.png",dpi=180,bbox_inches="tight"); plt.close(table_fig)
    ax2.margins(x=.12,y=.12)
    if handles: ax2.legend(handles=list(handles.values()),labels=list(handles.keys()),loc="upper left",bbox_to_anchor=(1.02,1.0),borderaxespad=0.)
    fig2.tight_layout(rect=(0,0,.82,.92)); fig2.savefig(out/"recommended_placement.png",dpi=180); figs.append(fig2)

    fig3,ax3=plt.subplots(figsize=(8,4))
    if result.modal_response_data is not None:
        data=result.modal_response_data; ax3.plot(data["frequencies_hz"],data["response_db"],label="Best coherent bass placement")
        if "exact_response_db" in data: ax3.plot(data["frequencies_hz"],data["exact_response_db"],alpha=.7,ls="--",label="Exact listener point")
        if np.isfinite(data.get("schroeder_frequency_hz",float("nan"))):
            ax3.axvline(data["schroeder_frequency_hz"],color="black",ls=":",label="Schroeder {:.0f} Hz".format(data["schroeder_frequency_hz"]))
        poor=data.get("poor_response")
        if poor is not None: ax3.plot(poor["frequencies_hz"],poor["response_db"],alpha=.7,label="Lowest-scoring single candidate")
        ax3.set(xlabel="Frequency (Hz)",ylabel="Relative pressure (dB)",title="Rectangular-room bass modal response"); ax3.legend()
    elif result.rir is not None:
        t=np.arange(len(result.rir))/result.fs*1000; n=min(len(t),int(.15*result.fs)); ax3.plot(t[:n],result.rir[:n],lw=.8); arrival=direct_arrival(result.rir,result.fs)/result.fs*1000
        ax3.axvspan(arrival,min(arrival+50,t[n-1] if n else arrival),color="orange",alpha=.2,label="50 ms clarity window"); ax3.set(xlabel="Time (ms)",ylabel="Amplitude",title="Recommended speaker room impulse response"); ax3.legend()
    else: ax3.set_visible(False)
    fig3.tight_layout(); fig3.savefig(out/"best_response.png",dpi=180); figs.append(fig3)
    if show: plt.show()
    else:
        for item in figs: plt.close(item)
    result_paths=[out/"candidate_speakers.png",out/"recommended_placement.png",out/"best_response.png"]
    if coord_rows: result_paths.append(out/"speaker_table.png")
    return result_paths


def plot_model_comparison(first,second,model_ids,output_dir="output",role=None):
    """Overlay equal-room placement results for two speaker model choices."""
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); fig,ax=plt.subplots(figsize=(9,6))
    _base(ax,first,"Speaker model comparison")
    colors=("orangered","royalblue")
    for model_index,(result,model_id,color) in enumerate(zip((first,second),model_ids,colors)):
        chosen=[s for s in result.best_pair.get("speakers",[]) if role is None or s["type"]==role]
        for speaker in chosen:
            pt=np.asarray(speaker["position_m"])/.3048
            ax.scatter(*pt,s=105,c=color,edgecolors="black",alpha=.8,marker="o" if model_index==0 else "s",label=model_id)
            aim=np.asarray(speaker.get("aim_direction",speaker.get("normal")))
            ax.annotate("",xy=pt+.45*aim/.3048,xytext=pt,arrowprops=dict(arrowstyle="->",color=color,lw=1.4))
            center=float(np.mean(first.room_polygon_m[0]/.3048)); dx=-8 if pt[0]<center else 8; dy=-30-model_index*18
            ax.annotate("{} ({:+.0f}°)".format(model_id.replace("generic_",""),speaker.get("toe_in_deg",0.)),xy=pt,xytext=(dx,dy),textcoords="offset points",ha="right" if dx<0 else "left",va="top",fontsize=7,bbox={"facecolor":"white","edgecolor":"none","alpha":.92,"pad":1})
    handles,labels=ax.get_legend_handles_labels(); unique={label:handle for handle,label in zip(handles,labels)}
    ax.legend(unique.values(),unique.keys(),loc="upper left",bbox_to_anchor=(1.02,1.0)); fig.tight_layout(rect=(0,0,.8,1))
    fig.text(.1,.02,"{} score: {:.2f} dB   |   {} score: {:.2f} dB".format(model_ids[0],first.best_pair["score_db"],model_ids[1],second.best_pair["score_db"]),fontsize=9)
    path=out/"model_comparison.png"; fig.savefig(path,dpi=180); plt.close(fig); return path


def plot_wall_height_heatmaps(layout, output_dir="output"):
    """Render acoustic candidate score over along-wall distance and mount height."""
    from pathlib import Path
    import matplotlib.pyplot as plt
    rows=layout.get("candidate_scores",[])
    if not rows: return None
    roles=list(dict.fromkeys(row["type"] for row in rows))
    from matplotlib.colors import Normalize
    from matplotlib.colorbar import ColorbarBase
    wall_count=max((int(row["wall_index"])+1 for row in rows),default=4)
    fig,axes=plt.subplots(len(roles),wall_count,figsize=(max(10,3.25*wall_count),max(3,2.8*len(roles))),squeeze=False)
    for row_index,role in enumerate(roles):
        role_rows=[row for row in rows if row["type"]==role]
        scores=np.asarray([row["score_db"] for row in role_rows],dtype=float)
        lo,span=float(scores.min()),float(np.ptp(scores)); norm=(scores-lo)/(span if span>1e-12 else 1.)
        for wall in range(wall_count):
            ax=axes[row_index,wall]; subset=[(row,norm[i]) for i,row in enumerate(role_rows) if row["wall_index"]==wall]
            if subset:
                points=np.asarray([[row["wall_u_m"],row["height_m"]] for row,_ in subset])
                colors=[value for _,value in subset]
                artist=ax.scatter(points[:,0],points[:,1],c=colors,cmap="viridis",vmin=0.,vmax=1.,s=18,marker="s")
                for speaker in layout["speakers"]:
                    if speaker["type"]==role and speaker["wall_index"]==wall:
                        ax.scatter([speaker["wall_u_m"]],
                                   [speaker["position_m"][2]],marker="*",s=100,c="red",edgecolors="white",linewidths=.5)
            ax.set(title="{} · wall {}".format(role,wall),xlabel="u along wall (m)",ylabel="mount height z (m)")
    fig.subplots_adjust(right=.88,wspace=.35,hspace=.42)
    color_axis=fig.add_axes([.91,.22,.015,.56])
    ColorbarBase(color_axis,cmap="viridis",norm=Normalize(0.,1.),label="Relative score (brighter = better)")
    fig.suptitle("Per-wall placement score by position and height")
    path=Path(output_dir)/"height_heatmaps.png"; path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=160); plt.close(fig)
    return path


def plot_seat_bass_response(result, output_dir="output", axial_modes_hz=None):
    """Plot exact-seat responses emitted by the joint modal bass evaluator."""
    placement=next((row for row in result.placements_by_type if row["type"]=="bass"),None)
    if placement is None or not placement["best"].get("modal_response"): return None
    data=placement["best"]["modal_response"]
    curves=np.asarray(data.get("seat_response_db",[]),dtype=float)
    freq=np.asarray(data.get("frequencies_hz",[]),dtype=float)
    if curves.ndim!=2 or curves.shape[1]!=freq.size: return None
    fig,ax=plt.subplots(figsize=(8,4))
    for index,row in enumerate(curves): ax.plot(freq,row,label="seat {}".format(index+1),lw=1.1)
    for index,frequency in enumerate(axial_modes_hz or []):
        if freq.size and freq[0]<=frequency<=freq[-1]:
            ax.axvline(frequency,color="black",alpha=.35,ls=":" ,lw=.8,label="axial mode" if index==0 else None)
    ax.set(xlabel="Frequency (Hz)",ylabel="Relative pressure (dB)",title="Bass response by modeled seat")
    ax.grid(alpha=.2); ax.legend(ncol=2,fontsize=8); fig.tight_layout()
    path=Path(output_dir)/"seat_bass_response.png"; path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180); plt.close(fig); return path


def plot_sub_strategy_comparison(strategies, output_dir="output"):
    """Compare seat variation, worst modeled null, and average modal level."""
    if not strategies: return None
    names=[item["strategy"] for item in strategies]
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,title,color in zip(axes,("seat_std_db","worst_null_db","mean_level_db"),
                                  ("Seat-to-seat std dev (dB)","Worst seat null (dB)","Mean response (dB)"),
                                  ("#527da8","#c45d52","#639b71")):
        values=[item[key] for item in strategies]; ax.bar(np.arange(len(values)),values,color=color)
        ax.set(title=title,xticks=np.arange(len(names)),xticklabels=names); ax.tick_params(axis="x",labelrotation=35,labelsize=7); ax.grid(axis="y",alpha=.2)
    fig.suptitle("Reference sub strategies (modal model)"); fig.tight_layout()
    path=Path(output_dir)/"sub_strategy_comparison.png"; path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180); plt.close(fig); return path


def plot_bass_management_response(setup, output_dir="output"):
    """Plot optimized summed crossover magnitude and phase for each seat."""
    if setup.get("status")!="estimated": return None
    f=np.asarray(setup["frequencies_hz"],dtype=float)
    db=np.asarray(setup["seat_response_db"],dtype=float)
    phase=np.asarray(setup["seat_phase_deg"],dtype=float)
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
    for label,level,angle in zip(setup["seat_labels"],db,phase):
        axes[0].plot(f,level,label=label,lw=1.2)
        axes[1].plot(f,angle,label=label,lw=1.1)
    axes[0].axvline(setup["crossover_hz"],color="black",ls=":",lw=1)
    axes[0].set(ylabel="Summed magnitude (dB)",title="Estimated LR4 bass-management response")
    axes[1].set(xlabel="Frequency (Hz)",ylabel="Unwrapped phase (degrees)")
    for ax in axes: ax.grid(alpha=.2)
    axes[0].legend(ncol=4,fontsize=8); fig.tight_layout()
    path=Path(output_dir)/"bass_management_response.png"; path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180); plt.close(fig); return path


def plot_channel_table(scene, output_dir="output"):
    """Render one row per placed channel, including separately searched ceiling speakers."""
    rows=[]
    by_channel={item["channel"]:item for item in scene.get("compliance",[])}
    for speaker in scene.get("speakers",[]):
        point=np.asarray(speaker["position_m"],dtype=float); check=by_channel.get(speaker["channel"],{})
        az=check.get("azimuth_deg","N/A"); el=check.get("elevation_deg","N/A")
        fmt=lambda value:"N/A" if isinstance(value,str) else "{:+.1f}°".format(value)
        rows.append([speaker["channel"],speaker["model_id"],"{:.2f}".format(point[0]/.3048),
            "{:.2f}".format(point[1]/.3048),"{:.2f}".format(point[2]/.3048),fmt(az),fmt(el),
            "{:.2f}".format(speaker.get("distance_m",float("nan"))),
            "{:.2f}".format(speaker.get("receiver_delay_ms",float("nan"))),
            "{:+.1f}".format(speaker.get("receiver_trim_db",0.)),check.get("status","—")])
    if not rows: return None
    fig,ax=plt.subplots(figsize=(13,max(3.,1.4+.34*len(rows)))); ax.axis("off")
    table=ax.table(cellText=rows,colLabels=["Channel","Model","X ft","Y ft","Z ft","Az","El","Distance m","Delay ms","Trim dB","Compliance"],
                   loc="center",cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(7.5); table.scale(1,1.4)
    fig.tight_layout(); path=Path(output_dir)/"speaker_table.png"; path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180,bbox_inches="tight"); plt.close(fig); return path


def plot_ceiling_heatmaps(scene, output_dir="output"):
    """Render per-channel legal ceiling-grid scores without duplicating wall panels."""
    rows=[item for item in scene.get("speakers",[]) if item.get("surface")=="ceiling" and item.get("ceiling_candidates")]
    if not rows: return None
    fig,axes=plt.subplots(1,len(rows),figsize=(4.1*len(rows),4),squeeze=False)
    for ax,speaker in zip(axes[0],rows):
        points=speaker["ceiling_candidates"]; xy=np.asarray([[row["x_m"],row["y_m"]] for row in points]); values=np.asarray([row["score"] for row in points])
        sc=ax.scatter(xy[:,0]/.3048,xy[:,1]/.3048,c=values,cmap="viridis",s=20)
        pos=np.asarray(speaker["position_m"]); ax.scatter([pos[0]/.3048],[pos[1]/.3048],marker="*",s=100,c="red",edgecolors="white")
        ax.set(title=speaker["channel"],xlabel="x (ft)",ylabel="y (ft)"); ax.set_aspect("equal"); fig.colorbar(sc,ax=ax,label="negative normalized angle error")
    fig.suptitle("Overhead channel ceiling-grid search"); fig.tight_layout()
    path=Path(output_dir)/"ceiling_heatmaps.png"; path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=180); plt.close(fig); return path


def plot_model_specs(model, output_dir="output", modal_data=None):
    """Save polar/directivity and on-axis/optional room-response plots."""
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    angles=np.linspace(0,180,361); fig,ax=plt.subplots(figsize=(7,4.5))
    if model.polar_table is not None:
        first=model._polar_rows()[0]; band_frequencies=sorted(float(key) for key in first if key!="angle_deg")
    else: band_frequencies=(500.,1000.,2000.,4000.)
    for frequency in band_frequencies:
        ax.plot(angles,[model.gain_db(angle,frequency_hz=frequency) for angle in angles],label="{} Hz".format(int(frequency)))
    ax.set(xlabel="Off-axis angle (degrees)",ylabel="Relative gain (dB)",title="{} horizontal directivity".format(model.model_id),ylim=(-40,1)); ax.grid(alpha=.25); ax.legend()
    polar_path=out/"{}_polar.png".format(model.model_id); fig.tight_layout(); fig.savefig(polar_path,dpi=180); plt.close(fig)
    frequencies=np.geomspace(20.,20000.,800); response=np.asarray(model.response_db(frequencies),dtype=float)
    fig,ax=plt.subplots(figsize=(8,4.5)); ax.semilogx(frequencies,response,label="On-axis specification")
    if modal_data is not None: ax.plot(modal_data["frequencies_hz"],modal_data["response_db"],label="Combined room response at listener")
    ax.set(xlabel="Frequency (Hz)",ylabel="Relative level (dB)",title="{} frequency response".format(model.model_id),xlim=(20,20000),ylim=(-50,5)); ax.grid(which="both",alpha=.2); ax.legend()
    response_path=out/"{}_response.png".format(model.model_id); fig.tight_layout(); fig.savefig(response_path,dpi=180); plt.close(fig)
    return [polar_path,response_path]
