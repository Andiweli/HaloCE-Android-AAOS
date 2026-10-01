/* Original-menu-style captions, rendered as graphic labels rather than the
   unrelated large_ui body font. The source cache/map is never modified. */
#include "android_caption_masks.h"
static struct bitmap_data *av_caption_bitmaps[15];
static void av_caption_dispose(void)
{
    int i;for(i=0;i<15;i++)if(av_caption_bitmaps[i]) {
        bitmap_delete(av_caption_bitmaps[i]);av_caption_bitmaps[i]=NULL;
    }
}
static boolean av_render_caption(struct widget_instance *widget,
    struct ui_widget_definition *definition,point2d offset,boolean focus)
{
    int i=av_index(widget->definition_tag_index),language=0,index,x,y,pos=0;
    struct av_caption_mask const *mask;struct bitmap_data *bitmap;
    rectangle2d bounds,source;unsigned char const *rle;unsigned long color;
    if(i<0 || !av_nodes[i].caption_style)return FALSE;
    switch(XGetLanguage()) {
        case XC_LANGUAGE_GERMAN:language=1;break;case XC_LANGUAGE_FRENCH:language=2;break;
        case XC_LANGUAGE_SPANISH:language=3;break;case XC_LANGUAGE_ITALIAN:language=4;break;
        /* A Japanese map supplies its own script font; keep that text route. */
        case XC_LANGUAGE_JAPANESE:return FALSE;
    }
    if(!widget->visible)return TRUE;
    index=language+(av_nodes[i].caption_style==2?(focus?10:5):0);mask=&av_caption_masks[index];
    bitmap=av_caption_bitmaps[index];
    if(!bitmap) {
        bitmap=bitmap_2d_new(512,64,0,11); /* engine a8r8g8b8, CPU-owned */
        if(!bitmap || !bitmap->base_address) {if(bitmap)bitmap_delete(bitmap);return FALSE;}
        memset(bitmap->base_address,0,512*64*4);rle=mask->rle;
        while(pos<mask->width*mask->height) {
            int count=*rle++,red=*rle++,green=*rle++,blue=*rle++,alpha=*rle++;
            while(count-- && pos<mask->width*mask->height) {
                x=pos%mask->width;y=pos/mask->width;
                *(pixel32 *)bitmap_2d_address(bitmap,(short)x,(short)y,0)=((pixel32)alpha<<24)|((pixel32)red<<16)|((pixel32)green<<8)|blue;pos++;
            }
        }
        bitmap_rebuild(bitmap);av_caption_bitmaps[index]=bitmap;
    }
    source.x0=source.y0=0;source.x1=mask->width;source.y1=mask->height;
    if(av_nodes[i].caption_style==2) {
        bounds.x0=definition->bounds.x0+offset.x+(definition->bounds.x1-definition->bounds.x0-mask->width)/2;
        bounds.y0=definition->bounds.y0+offset.y;
        color=0x00ffffff;
    } else {
        /* Heading artwork has 28px left padding and ink at y=33. */
        bounds.x0=definition->bounds.x0+offset.x+28;
        bounds.y0=definition->bounds.y0+offset.y+28;color=0x00ffffff;
    }
    bounds.x1=bounds.x0+mask->width;bounds.y1=bounds.y0+mask->height;
    color|=(unsigned long)(widget_instance_get_cumulative_alpha_modifier(widget)*255.0f)<<24;
    /* Match the main-menu background renderer's focused plasma contribution. */
    real_argb_color saved_plasma=ui_plasma_effect_color;
    if(av_nodes[i].caption_style==2 && focus) {
        ui_plasma_effect_color.alpha=0.0f;
        ui_plasma_effect_color.red=ui_plasma_effect_color.green=ui_plasma_effect_color.blue=0.05f;
    }
    draw_bitmap_in_rect(bitmap,&bounds,&source,NULL,color,NULL,av_nodes[i].caption_style!=2);
    ui_plasma_effect_color=saved_plasma;
    return TRUE;
}
