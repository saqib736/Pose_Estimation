import cv2
import heapq
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

from .utils import get_hr_conf,get_arrow_map,nan2zero_dict
from .utils import get_pifmap,get_pafmap, restore_pif_maps, restore_paf_maps
from ..human import Human,BodyPart
from ..processor import BasicVisualizer
from ..processor import BasicPreProcessor
from ..processor import BasicPostProcessor
from ..processor import PltDrawer
from ..common import to_numpy_dict, image_float_to_uint8

class PreProcessor(BasicPreProcessor):
    def __init__(self,parts,limbs,hin,win,hout,wout,colors=None,data_format="channels_first", *args, **kargs):
        self.hin=hin
        self.win=win
        self.hout=hout
        self.wout=wout
        self.parts=parts
        self.limbs=limbs
        self.data_format=data_format
        self.colors=colors if (colors!=None) else (len(self.parts)*[[0,255,0]])

    def process(self,annos, mask, bbxs):
        mask_out=cv2.resize(mask[0],(self.wout,self.hout))
        pif_conf,pif_vec,pif_bmin,pif_scale = get_pifmap(annos, mask_out, self.hin, self.win, self.hout, self.wout, self.parts, self.limbs, data_format=self.data_format)
        paf_conf,paf_src_vec,paf_dst_vec,paf_src_bmin,paf_dst_bmin,paf_src_scale,paf_dst_scale = get_pafmap(annos, mask_out, self.hin, self.win, self.hout, self.wout, self.parts, self.limbs, data_format=self.data_format)
        target_x = {
            "pif_conf": pif_conf,
            "pif_vec": pif_vec,
            "pif_bmin": pif_bmin,
            "pif_scale": pif_scale,
            "paf_conf": paf_conf,
            "paf_src_vec": paf_src_vec,
            "paf_dst_vec": paf_dst_vec,
            "paf_src_bmin": paf_src_bmin,
            "paf_dst_bmin": paf_dst_bmin,
            "paf_src_scale": paf_src_scale,
            "paf_dst_scale": paf_dst_scale
        }
        return target_x

class PostProcessor(BasicPostProcessor):
    def __init__(self,parts,limbs,hin,win,hout,wout,colors=None,thresh_pif=0.3,thresh_paf=0.1,thresh_ref_pif=0.3,thresh_ref_paf=0.1,\
        thresh_gen_ref_pif=0.1,part_num_thresh=4,score_thresh=0.1,reduction=2,min_scale=4,greedy_match=True,reverse_match=True,\
            data_format="channels_first",debug=False, *args, **kargs):
        self.parts=parts
        self.limbs=limbs
        self.colors=colors if (colors!=None) else (len(self.parts)*[[0,255,0]])
        self.n_pos=len(self.parts)
        self.n_limbs=len(self.limbs)
        self.hin=hin
        self.win=win
        self.hout=hout
        self.wout=wout
        self.stride=int(self.hin/self.hout)
        self.thresh_pif=thresh_pif
        self.thresh_paf=thresh_paf
        self.thresh_ref_pif=thresh_ref_pif
        self.thresh_ref_paf=thresh_ref_paf
        self.thresh_gen_ref_pif=thresh_gen_ref_pif
        self.part_num_thresh=part_num_thresh
        self.score_thresh=score_thresh
        self.reduction=reduction
        self.min_scale=min_scale
        self.greedy_match=greedy_match
        self.reverse_match=reverse_match
        self.data_format=data_format
        self.debug=debug
        #by source generation
        self.by_source=defaultdict(dict)
        for limb_idx,(src_idx,dst_idx) in enumerate(self.limbs):
            self.by_source[src_idx][dst_idx]=(limb_idx,True)
            self.by_source[dst_idx][src_idx]=(limb_idx,False)
        #TODO:whether add score weight for each parts
    
    def process(self, predict_x, resize=True):
        predict_x = to_numpy_dict(predict_x)
        batch_size = list(predict_x.values())[0].shape[0]
        humans_list = []
        for batch_idx in range(0,batch_size):
            predict_x_one = {key:value[batch_idx] for key,value in predict_x.items()}
            humans_list.append(self.process_one(predict_x_one, resize=resize))        
        return humans_list

    def process_one(self,predict_x, resize=True):
        # shape:
        # conf_map:[field_num,hout,wout]
        # vec_map:[field_num,2,hout,wout]
        # scale_map:[field_num,hout,wout]
        # decode pif_maps,paf_maps
        pif_conf, pif_vec, pif_scale = predict_x["pif_conf"], predict_x["pif_vec"], predict_x["pif_scale"]
        paf_conf, paf_src_vec, paf_dst_vec, paf_src_scale, paf_dst_scale = predict_x["paf_conf"], predict_x["paf_src_vec"],\
                                            predict_x["paf_dst_vec"], predict_x["paf_src_scale"], predict_x["paf_dst_scale"]
        self.debug_print(f"exam pif shapes: pif_conf:{pif_conf.shape} pif_vec:{pif_vec.shape} pif_scale:{pif_scale.shape}")
        self.debug_print(f"exam paf shapes: paf_conf:{paf_conf.shape} paf_src_vec:{paf_src_vec.shape} paf_dst_vec:{paf_dst_vec.shape} "\
            +f"paf_src_scale:{paf_src_scale.shape} paf_dst_scale:{paf_dst_scale.shape}")
        
        # restore maps
        pif_vec, pif_scale = restore_pif_maps(pif_vec_map_batch=pif_vec, pif_scale_map_batch=pif_scale, stride=self.stride)
        paf_src_vec, paf_dst_vec, paf_src_scale, paf_dst_scale = restore_paf_maps(paf_src_vec_map_batch=paf_src_vec,\
                        paf_dst_vec_map_batch=paf_dst_vec, paf_src_scale_map_batch=paf_src_scale,\
                        paf_dst_scale_map_batch=paf_dst_scale, stride=self.stride)

        #get pif_hr_conf
        pif_hr_conf=get_hr_conf(pif_conf,pif_vec,pif_scale,stride=self.stride,thresh=self.thresh_gen_ref_pif,debug=False)
        self.debug_print(f"test hr_conf")
        for pos_idx in range(0,self.n_pos):
            self.debug_print(f"test hr_conf idx:{pos_idx} max_conf:{np.max(pif_conf[pos_idx])} max_hr_conf:{np.max(pif_hr_conf[pos_idx])}")
        #generate pose seeds according to refined pif_conf
        seeds=[]
        for pos_idx in range(0,self.n_pos):
            mask_conf=pif_conf[pos_idx]>self.thresh_pif
            cs=pif_conf[pos_idx,mask_conf]
            xs=pif_vec[pos_idx,0,mask_conf]
            ys=pif_vec[pos_idx,1,mask_conf]
            scales=pif_scale[pos_idx,mask_conf]
            hr_cs=self.field_to_scalar(xs,ys,pif_hr_conf[pos_idx])
            ref_cs=0.9*hr_cs+0.1*cs
            mask_ref_conf=ref_cs>self.thresh_ref_pif
            for ref_c,x,y,scale in zip(ref_cs[mask_ref_conf],xs[mask_ref_conf],ys[mask_ref_conf],scales[mask_ref_conf]):
                seeds.append((ref_c,pos_idx,x,y,scale))
                #print(f"seed gen pos_idx:{pos_idx} ref_c:{ref_c} x:{x} y:{y} scale:{scale}")
        self.debug_print(f"test before sort len_seeds:{len(seeds)}")
        seeds=sorted(seeds,reverse=True)
        self.debug_print(f"test after sort len_seeds:{len(seeds)}")
        #generate connection seeds according to paf_map
        cif_floor=0.1
        forward_list=[]
        backward_list=[]
        for limb_idx in range(0,self.n_limbs):
            src_idx,dst_idx=self.limbs[limb_idx]
            mask_conf=paf_conf[limb_idx]>self.thresh_paf
            score=paf_conf[limb_idx,mask_conf]
            src_x=paf_src_vec[limb_idx,0,mask_conf]
            src_y=paf_src_vec[limb_idx,1,mask_conf]
            dst_x=paf_dst_vec[limb_idx,0,mask_conf]
            dst_y=paf_dst_vec[limb_idx,1,mask_conf]
            src_scale=paf_src_scale[limb_idx,mask_conf]
            dst_scale=paf_dst_scale[limb_idx,mask_conf]
            #generate backward (merge score with the src pif_score)
            cifhr_b=self.field_to_scalar(src_x,src_y,pif_hr_conf[src_idx])
            score_b=score*(cif_floor+(1-cif_floor)*cifhr_b)
            mask_b=score_b>self.thresh_ref_paf
            backward_list.append([score_b[mask_b],dst_x[mask_b],dst_y[mask_b],dst_scale[mask_b],src_x[mask_b],src_y[mask_b],src_scale[mask_b]])
            #generate forward connections (merge score with the dst pif_score)
            cifhr_f=self.field_to_scalar(dst_x,dst_y,pif_hr_conf[dst_idx])
            score_f=score*(cif_floor+(1-cif_floor)*cifhr_f)
            mask_f=score_f>self.thresh_ref_paf
            forward_list.append([score_f[mask_f],src_x[mask_f],src_y[mask_f],src_scale[mask_f],dst_x[mask_f],dst_y[mask_f],dst_scale[mask_f]])
            #debug
            mask_all=np.sum(mask_conf)
            self.debug_print(f"test limb_gen limb_idx:{limb_idx} {self.parts(self.limbs[limb_idx][0])}-{self.parts(self.limbs[limb_idx][1])} max_conf:{np.max(paf_conf[limb_idx])} mask_all:{mask_all}")
            if(mask_all>0):
                self.debug_print(f"test bk_list_gen: limb_idx:{limb_idx} max_score:{np.max(score)} max_cifhr_b:{np.max(cifhr_b)} max_score_b:{np.max(score_b)} mask_num_b：{np.sum(mask_b)}")
                self.debug_print(f"test fw_list_gen: limb_idx:{limb_idx} max_score:{np.max(score)} max_cifhr_f:{np.max(cifhr_f)} max_score_f:{np.max(score_f)} mask_num_f:{np.sum(mask_f)}")
            self.debug_print("")
        #greedy assemble
        #TODO: further check!
        occupied=np.zeros(shape=(self.n_pos,int(pif_hr_conf.shape[1]/self.reduction),int(pif_hr_conf.shape[2]/self.reduction)))
        annotations=[]
        self.debug_print(f"test seeds_num:{len(seeds)}")
        for c,pos_idx,x,y,scale in seeds:
            check_occupy=self.check_occupy(occupied,pos_idx,x,y,reduction=self.reduction)
            if(check_occupy):
                continue
            #ann meaning: ann[0]=conf ann[1]=x ann[2]=y ann[3]=scale
            ann=np.zeros(shape=(self.n_pos,4))
            ann[:,0]=-1.0
            ann[pos_idx]=np.array([c,x,y,scale])
            ann=self.grow(ann,forward_list,backward_list,reverse_match=self.reverse_match)
            annotations.append(ann)
            #put the ann into occupacy
            for ann_pos_idx in range(0,self.n_pos):
                occupied=self.put_occupy(occupied,ann_pos_idx,ann[ann_pos_idx,1],ann[ann_pos_idx,2],ann[ann_pos_idx,3],\
                    reduction=self.reduction,min_scale=self.min_scale)
        #point-wise nms
        if(len(annotations)!=0):
            annotations=self.kpt_nms(annotations)
        #convert to humans
        ret_humans=[]
        for ann_idx,ann in enumerate(annotations):
            self.debug_print(f"\nchecking human found:{ann_idx}")
            ret_human=Human(parts=self.parts,limbs=self.limbs,colors=self.colors)
            for pos_idx in range(0,self.n_pos):
                score,x,y,scale=ann[pos_idx]
                if(score>0.0):
                    self.debug_print(f"{self.parts(pos_idx)} x:{x} y:{y} scale:{scale} score:{score}")
                    ret_human.body_parts[pos_idx]=BodyPart(parts=self.parts,u_idx=f"{ann_idx}-{pos_idx}",part_idx=pos_idx,\
                        x=x,y=y,score=score)
            #check for num
            if(ret_human.get_partnum()<self.part_num_thresh):
                continue
            if(ret_human.get_score()<self.score_thresh):
                continue
            self.debug_print(f"human found!")
            ret_humans.append(ret_human)
            self.debug_print("")
        self.debug_print(f"total {len(ret_humans)} human detected!")
        return ret_humans

    def debug_print(self,msg, debug=False):
        if(self.debug or debug):
            print(msg)

    #convert vector field to scalar
    def field_to_scalar(self,vec_x,vec_y,scalar_map,debug=False):
        #scalar_map shape:[height,width]
        #vec_map shape:[2,vec_num]
        h,w=scalar_map.shape
        vec_num=vec_x.shape[0]
        ret_scalar=np.zeros(vec_num)
        for vec_idx in range(0,vec_num):
            x,y=np.round(vec_x[vec_idx]).astype(np.int32),np.round(vec_y[vec_idx]).astype(np.int32)
            if(x>=0 and x<w and y>=0 and y<h):
                ret_scalar[vec_idx]=scalar_map[y,x]
        return ret_scalar

    #check whether the position is occupied
    def check_occupy(self,occupied,pos_idx,x,y,reduction=2):
        _,field_h,field_w=occupied.shape
        x,y=np.round(x/reduction).astype(np.int32),np.round(y/reduction).astype(np.int32)
        if(x<0 or x>=field_w or y<0 or y>=field_h):
            return True
        if(occupied[pos_idx,y,x]!=0):
            return True
        else:
            return False

    #mark the postion as occupied
    def put_occupy(self,occupied,pos_idx,x,y,scale,reduction=2,min_scale=4,value=1):
        _,field_h,field_w=occupied.shape
        x,y=np.round(x/reduction),np.round(y/reduction)
        size=np.round(max(min_scale/reduction,scale/reduction))
        min_x=max(0,int(x-size))
        max_x=max(min_x+1,min(field_w,int(x+size)+1))
        min_y=max(0,int(y-size))
        max_y=max(min_y+1,min(field_h,int(y+size)+1))
        occupied[pos_idx,min_y:max_y,min_x:max_x]+=value
        return occupied

    #keypoint-wise nms
    def kpt_nms(self,annotations):
        max_x=int(max([np.max(ann[:,1]) for ann in annotations])+1)
        max_y=int(max([np.max(ann[:,2]) for ann in annotations])+1)
        occupied=np.zeros(shape=(self.n_pos,max_y,max_x))
        annotations=sorted(annotations,key=lambda ann: -np.sum(ann[:,0]))
        for ann in annotations:
            for pos_idx in range(0,self.n_pos):
                _,x,y,scale=ann[pos_idx]
                if(self.check_occupy(occupied,pos_idx,x,y,reduction=2)):
                    ann[pos_idx,0]=0
                else:
                    self.put_occupy(occupied,pos_idx,x,y,scale,reduction=2,min_scale=4)
        annotations=sorted(annotations,key=lambda ann: -np.sum(ann[:,0]))
        return annotations

    #get closest matching connection and blend them
    def find_connection(self,connections,x,y,scale,connection_method="blend",thresh_second=0.01):
        sigma_filter=2.0*scale
        sigma_gaussian=0.25*(scale**2)
        first_idx,first_score=-1,0.0
        second_idx,second_score=-1,0.0
        #traverse connections to find the highest score connection weighted by distance
        score_f,src_x,src_y,src_scale,dst_x,dst_y,dst_scale=connections
        con_num=score_f.shape[0]
        for con_idx in range(0,con_num):
            con_score=score_f[con_idx]
            con_src_x,con_src_y,_=src_x[con_idx],src_y[con_idx],src_scale[con_idx]
            #ignore connections with src_kpts too distant
            if(x<con_src_x-sigma_filter or x>con_src_x+sigma_filter):
                continue
            if(y<con_src_y-sigma_filter or y>con_src_y+sigma_filter):
                continue
            distance=(con_src_x-x)**2+(con_src_y-y)**2
            w_score=np.exp(-0.5*distance/sigma_gaussian)*con_score
            #replace to find the first and second match connections
            if(w_score>first_score):
                second_idx=first_idx
                second_score=first_score
                first_idx=con_idx
                first_score=w_score
            elif(w_score>second_score):
                second_idx=con_idx
                second_score=w_score
        #not find match connections
        if(first_idx==-1 or first_score==0.0):
            return 0.0,0.0,0.0,0.0
        #method max:
        if(connection_method=="max"):
            return first_score,dst_x[first_idx],dst_y[first_idx],dst_scale[first_idx]
        #method blend:
        elif(connection_method=="blend"):
            #ignore second connection with score too slow
            if(second_idx==-1 or second_score<thresh_second or second_score<0.5*first_score):
                return first_score*0.5,dst_x[first_idx],dst_y[first_idx],dst_scale[first_idx]
            #ignore second connection too distant from the first one
            dist_first_second=(dst_x[first_idx]-dst_x[second_idx])**2+(dst_y[first_idx]-dst_y[second_idx])**2
            if(dist_first_second>(dst_scale[first_idx]**2/4.0)):
                return first_score*0.5,dst_x[first_idx],dst_y[first_idx],dst_scale[first_idx]
            #otherwise return the blended two connection
            blend_score=0.5*(first_score+second_score)
            blend_x=(dst_x[first_idx]*first_score+dst_x[second_idx]*second_score)/(first_score+second_score)
            blend_y=(dst_y[first_idx]*first_score+dst_y[second_idx]*second_score)/(first_score+second_score)
            blend_scale=(dst_scale[first_idx]*first_score+dst_scale[second_idx]*second_score)/(first_score+second_score)
            return blend_score,blend_x,blend_y,blend_scale

    #get connection given a part, forwad_list and backward_list generated from paf maps
    def get_connection(self,ann,src_idx,dst_idx,forward_list,backward_list,connection_method="blend",reverse_match=True):
        limb_idx,forward_flag=self.by_source[src_idx][dst_idx]
        if(forward_flag):
            forward_cons,backward_cons=forward_list[limb_idx],backward_list[limb_idx]
        else:
            forward_cons,backward_cons=backward_list[limb_idx],forward_list[limb_idx]
        self.debug_print(f"connecting {self.parts(src_idx)}-{self.parts(dst_idx)}")
        c,x,y,scale=ann[src_idx]
        #forward matching
        fc,fx,fy,fscale=self.find_connection(forward_cons,x,y,scale,connection_method=connection_method)
        if(fc==0.0):
            return 0.0,0.0,0.0,0.0
        merge_score=np.sqrt(fc*c)
        #reverse matching
        if(reverse_match):
            rc,rx,ry,_=self.find_connection(backward_cons,fx,fy,fscale,connection_method=connection_method)
            #couldn't find a reverse one
            if(rc==0.0):
                return 0.0,0.0,0.0,0.0
            #reverse finding is distant from the orginal founded one
            if abs(x-rx)+abs(y-ry)>scale:
                return 0.0,0.0,0.0,0.0
        #successfully found connection
        return merge_score,fx,fy,fscale

    #greedy matching pif seeds with forward and backward connections generated from paf maps
    def grow(self,ann,forward_list,backward_list,reverse_match=True):
        frontier = []
        in_frontier = set()
        #add the point to assemble frontier by_source
        def add_frontier(ann,src_idx):
            #traverse all the part that the current part connect to
            for dst_idx,(_,_) in self.by_source[src_idx].items():
                #ignore points that already assigned
                if(ann[dst_idx,0]>0):
                    continue
                #ignore limbs that already in the frontier
                if((src_idx,dst_idx) in in_frontier):
                    continue
                #otherwise put it into frontier
                self.debug_print(f"test adding frontier {self.parts(src_idx)}-{self.parts(dst_idx)} src_score:{ann[src_idx,0]} dst_score:{ann[dst_idx,0]}")
                max_possible_score=np.sqrt(ann[src_idx,0])
                heapq.heappush(frontier,(-max_possible_score,src_idx,dst_idx))
                in_frontier.add((src_idx,dst_idx))

        #find matching connections from frontier
        def get_frontier(ann):
            while frontier:
                pop_frontier=heapq.heappop(frontier)
                _,src_idx,dst_idx=pop_frontier
                #ignore points that assigned by other frontier
                if(ann[dst_idx,0]>0.0):
                    continue
                #find conection
                fc,fx,fy,fscale=self.get_connection(ann,src_idx,dst_idx,forward_list,backward_list,reverse_match=reverse_match)
                self.debug_print(f"get connection fc:{fc} fx:{fx} fy:{fy} fscale:{fscale}")
                if(fc==0.0):
                    continue
                return fc,fx,fy,fscale,src_idx,dst_idx
            return None

        #initially add joints to frontier
        self.debug_print("\nbegin grow!:")
        for pos_idx in range(0,self.n_pos):
            if(ann[pos_idx,0]>0.0):
                add_frontier(ann,pos_idx)
        #recurrently find the matched connections
        while True:
            find_match=get_frontier(ann)
            if(find_match==None):
                break
            score,x,y,scale,src_idx,dst_idx=find_match
            if(ann[dst_idx,0]>0.0):
                continue
            ann[dst_idx,0]=score
            ann[dst_idx,1]=x
            ann[dst_idx,2]=y
            ann[dst_idx,3]=scale
            self.debug_print(f"grow part:{self.parts(dst_idx)} score:{score} x:{x} y:{y} scale:{scale}\n")
            add_frontier(ann,dst_idx)
        #finished matching a person
        return ann

class Visualizer(BasicVisualizer):
    def __init__(self, save_dir="./save_dir", debug=False, *args, **kargs):
        self.save_dir = save_dir
        self.debug=debug
    
    def debug_print(self,msg, debug=False):
        if(self.debug or debug):
            print(msg)

    def visualize(self, image_batch, predict_x, mask_batch=None, humans_list=None, name="vis"):
        # mask
        if(mask_batch is None):
            mask_batch = np.ones_like(image_batch)
        # transform
        image_batch = np.transpose(image_batch,[0,2,3,1])
        mask_batch = np.transpose(mask_batch,[0,2,3,1])
        # defualt values
        # TODO: pass config values
        stride = 8

        # predict maps
        predict_x = nan2zero_dict(predict_x)
        pd_pif_conf_batch, pd_pif_vec_batch, pd_pif_scale_batch = predict_x["pif_conf"], predict_x["pif_vec"], predict_x["pif_scale"]
        pd_paf_conf_batch, pd_paf_src_vec_batch, pd_paf_dst_vec_batch, pd_paf_src_scale_batch, pd_paf_dst_scale_batch =\
             predict_x["paf_conf"], predict_x["paf_src_vec"], predict_x["paf_dst_vec"], predict_x["paf_src_scale"], predict_x["paf_dst_scale"]
        
        # restore maps
        # pif maps
        pd_pif_vec_batch, pd_pif_scale_batch = restore_pif_maps(pd_pif_vec_batch, pd_pif_scale_batch)
        self.debug_print(f"test pd_pif_vec_batch.shape:{pd_pif_vec_batch.shape}")
        # paf maps
        pd_paf_src_vec_batch, pd_paf_dst_vec_batch, pd_paf_src_scale_batch, pd_paf_dst_scale_batch = \
            restore_paf_maps(pd_paf_src_vec_batch, pd_paf_dst_vec_batch, pd_paf_src_scale_batch, pd_paf_dst_scale_batch)
        self.debug_print(f"test visualize shape: pd_paf_src_vec_batch:{pd_paf_src_vec_batch.shape}")
        self.debug_print(f"test visualize shape: pd_paf_dst_vec_batch:{pd_paf_dst_vec_batch.shape}")
        self.debug_print(f"test visualize shape: pd_paf_src_scale_batch:{pd_paf_src_scale_batch.shape}")
        self.debug_print(f"test visualize shape: pd_paf_dst_scale_batch:{pd_paf_dst_scale_batch.shape}")

        batch_size = image_batch.shape[0]
        for b_idx in range(0,batch_size):
            image, mask = image_batch[b_idx], mask_batch[b_idx]
            # pd map
            pd_pif_conf, pd_pif_vec, pd_pif_scale = pd_pif_conf_batch[b_idx], pd_pif_vec_batch[b_idx], pd_pif_scale_batch[b_idx]
            pd_paf_conf, pd_paf_src_vec, pd_paf_dst_vec = pd_paf_conf_batch[b_idx], pd_paf_src_vec_batch[b_idx], pd_paf_dst_vec_batch[b_idx]

            # draw maps
            # begin draw
            pltdrawer = PltDrawer(draw_row=2, draw_col=3, dpi=400)

            # draw origin image
            origin_image = image_float_to_uint8(image.copy())
            pltdrawer.add_subplot(origin_image, "origin_image")


            # draw pd_pif_conf
            pd_pif_conf_show = np.amax(pd_pif_conf, axis=0)
            pltdrawer.add_subplot(pd_pif_conf_show, "pd pif_conf", color_bar=True)

            # darw pd_pif_hr_conf
            pd_pif_hr_conf = get_hr_conf(pd_pif_conf, pd_pif_vec, pd_pif_scale, stride)
            pd_pif_hr_conf_show = np.amax(pd_pif_hr_conf, axis=0)
            # plt.imsave(f'{self.save_dir}/{name}', pd_pif_hr_conf_show)
            pltdrawer.add_subplot(pd_pif_hr_conf_show, "pd pif_hr_conf", color_bar=True)

            # draw mask
            pltdrawer.add_subplot(mask, "mask")

            # darw pd paf_conf
            pd_paf_conf_show = np.amax(pd_paf_conf, axis=0)
            pltdrawer.add_subplot(pd_paf_conf_show, "pd paf_conf", color_bar=True)

            # draw pd paf_vec
            hout, wout = pd_paf_conf.shape[1], pd_paf_conf.shape[2]
            pd_paf_vec_map_show = np.zeros(shape=(hout*stride,wout*stride,3)).astype(np.int8)
            pd_paf_vec_map_show = get_arrow_map(pd_paf_vec_map_show, pd_paf_conf, pd_paf_src_vec, pd_paf_dst_vec)
            pltdrawer.add_subplot(pd_paf_vec_map_show, "pd paf_vec")
            # save fig
            pltdrawer.savefig(f"{self.save_dir}/{name}_{b_idx}_paf.png")

            # draw results
            if(humans_list is not  None):
                humans = humans_list[b_idx]
                self.visualize_result(image, humans, f"{name}_{b_idx}_result")


    def visualize_compare(self, image_batch, predict_x, target_x, mask_batch=None, humans_list=None, name="vis"):
        # mask
        if(mask_batch is None):
            mask_batch = np.ones_like(image_batch)
        # transform
        image_batch = np.transpose(image_batch,[0,2,3,1])
        mask_batch = np.transpose(mask_batch,[0,2,3,1])
        # defualt values
        # TODO: pass config values
        stride = 8

        # predict maps
        predict_x = nan2zero_dict(predict_x)
        pd_pif_conf_batch, pd_pif_vec_batch, pd_pif_scale_batch = predict_x["pif_conf"], predict_x["pif_vec"], predict_x["pif_scale"]
        pd_paf_conf_batch, pd_paf_src_vec_batch, pd_paf_dst_vec_batch = predict_x["paf_conf"], predict_x["paf_src_vec"], predict_x["paf_dst_vec"]
        pd_paf_src_scale_batch, pd_paf_dst_scale_batch = predict_x["paf_src_scale"], predict_x["paf_dst_scale"]
        # target maps
        target_x = nan2zero_dict(target_x)
        gt_pif_conf_batch, gt_pif_vec_batch, gt_pif_scale_batch = target_x["pif_conf"], target_x["pif_vec"], target_x["pif_scale"]
        gt_paf_conf_batch, gt_paf_src_vec_batch, gt_paf_dst_vec_batch = target_x["paf_conf"], target_x["paf_src_vec"], predict_x["paf_dst_vec"]
        gt_paf_src_scale_batch, gt_paf_dst_scale_batch = target_x["paf_src_scale"], target_x["paf_dst_scale"]
        
        # restore maps
        # pif maps
        pd_pif_vec_batch, pd_pif_scale_batch = restore_pif_maps(pd_pif_vec_batch, pd_pif_scale_batch)
        gt_pif_vec_batch, gt_pif_scale_batch = restore_pif_maps(gt_pif_vec_batch, gt_pif_scale_batch)
        # paf maps
        pd_paf_src_vec_batch, pd_paf_dst_vec_batch, pd_paf_src_scale_batch, pd_paf_dst_scale_batch = \
            restore_paf_maps(pd_paf_src_vec_batch, pd_paf_dst_vec_batch, pd_paf_src_scale_batch, pd_paf_dst_scale_batch)
        gt_paf_src_vec_batch, gt_paf_dst_vec_batch, gt_paf_src_scale_batch, gt_paf_dst_scale_batch = \
            restore_paf_maps(gt_paf_src_vec_batch, gt_paf_dst_vec_batch, gt_paf_src_scale_batch, gt_paf_dst_scale_batch)

        batch_size = image_batch.shape[0]
        for b_idx in range(0,batch_size):
            image, mask = image_batch[b_idx], mask_batch[b_idx]
            # pd map
            pd_pif_conf, pd_pif_vec, pd_pif_scale = pd_pif_conf_batch[b_idx], pd_pif_vec_batch[b_idx], pd_pif_scale_batch[b_idx]
            pd_paf_conf, pd_paf_src_vec, pd_paf_dst_vec = pd_paf_conf_batch[b_idx], pd_paf_src_vec_batch[b_idx], pd_paf_dst_vec_batch[b_idx]
            # gt map
            gt_pif_conf, gt_pif_vec, gt_pif_scale = gt_pif_conf_batch[b_idx], gt_pif_vec_batch[b_idx], gt_pif_scale_batch[b_idx]
            gt_paf_conf, gt_paf_src_vec, gt_paf_dst_vec = gt_paf_conf_batch[b_idx], gt_paf_src_vec_batch[b_idx], gt_paf_dst_vec_batch[b_idx]
            # draw pif maps
            # begin draw
            pif_pltdrawer = PltDrawer(draw_row=2, draw_col=3, dpi=400)

            # draw origin image
            origin_image = image_float_to_uint8(image.copy())
            pif_pltdrawer.add_subplot(origin_image, "origin_image")

            # draw gt_pif_conf
            gt_pif_conf_show = np.amax(gt_pif_conf, axis=0)
            pif_pltdrawer.add_subplot(gt_pif_conf_show, "gt pif_conf", color_bar=True)

            # darw gt_pif_hr_conf
            gt_pif_hr_conf = get_hr_conf(gt_pif_conf, gt_pif_vec, gt_pif_scale, stride)
            gt_pif_hr_conf_show = np.amax(gt_pif_hr_conf, axis=0)
            pif_pltdrawer.add_subplot(gt_pif_hr_conf_show, "gt pif_hr_conf", color_bar=True)

            # draw mask
            pif_pltdrawer.add_subplot(mask, "mask")

            # draw pd_pif_conf
            pd_pif_conf_show = np.amax(pd_pif_conf, axis=0)
            pif_pltdrawer.add_subplot(pd_pif_conf_show, "pd pif_conf", color_bar=True)

            # darw pd_pif_hr_conf
            pd_pif_hr_conf = get_hr_conf(pd_pif_conf, pd_pif_vec, pd_pif_scale, stride)
            pd_pif_hr_conf_show = np.amax(pd_pif_hr_conf, axis=0)
            pif_pltdrawer.add_subplot(pd_pif_hr_conf_show, "pd pif_hr_conf", color_bar=True)

            # save fig
            pif_pltdrawer.savefig(f"{self.save_dir}/{name}_{b_idx}_pif.png")

            # draw paf maps
            # begin draw
            paf_pltdrawer = PltDrawer(draw_row=2, draw_col=3, dpi=400)

            # draw origin image
            paf_pltdrawer.add_subplot(image, "origin image")

            # draw gt paf_conf
            gt_paf_conf_show = np.amax(gt_paf_conf, axis=0)
            paf_pltdrawer.add_subplot(gt_paf_conf_show, "gt paf_conf", color_bar=True)

            # draw gt paf_vec_map
            hout, wout = gt_paf_src_vec.shape[-2], gt_paf_src_vec.shape[-1]
            gt_paf_vec_map_show = np.zeros(shape=(hout*stride,wout*stride,3)).astype(np.int8)
            gt_paf_vec_map_show = get_arrow_map(gt_paf_vec_map_show, gt_paf_conf, gt_paf_src_vec, gt_paf_dst_vec, debug=False)
            paf_pltdrawer.add_subplot(gt_paf_vec_map_show, "gt paf_vec")

            # draw mask
            paf_pltdrawer.add_subplot(mask, "mask")

            # darw pd paf_conf
            pd_paf_conf_show = np.amax(pd_paf_conf, axis=0)
            paf_pltdrawer.add_subplot(pd_paf_conf_show, "pd paf_conf", color_bar=True)

            # draw pd paf_vec
            hout, wout = pd_paf_src_vec.shape[-2], pd_paf_src_vec.shape[-1]
            pd_paf_vec_map_show = np.zeros(shape=(hout*stride,wout*stride,3)).astype(np.int8)
            pd_paf_vec_map_show = get_arrow_map(pd_paf_vec_map_show, pd_paf_conf, pd_paf_src_vec, pd_paf_dst_vec)
            paf_pltdrawer.add_subplot(pd_paf_vec_map_show, "pd paf_vec")

            # save fig
            paf_pltdrawer.savefig(f"{self.save_dir}/{name}_{b_idx}_paf.png")

            # draw results
            if(humans_list is not  None):
                humans = humans_list[b_idx]
                self.visualize_result(image, humans, f"{name}_{b_idx}_result")