/* The keyboard's button hints are baked into one DXT background. Locate the
   two short blue bars of each '=' in its footer, then sample a blank footer
   column in those strips. Neither the source pixels nor the map are changed. */
static int ak_blue_pixel(struct bitmap_data *b,int x,int y)
{
    unsigned char const *p=(unsigned char const *)b->base_address;
    unsigned long colors,bits;unsigned short c0,c1;int index,r,g,blue,a=255;
    if(!p || b->format<14 || b->format>16)return 0;
    p+=((y/4)*((b->width+3)/4)+x/4)*(b->format==14?8:16);
    index=(y%4)*4+x%4;
    if(b->format==15)a=((p[index/2]>>((index%2)*4))&15)*17;
    else if(b->format==16) {
        unsigned long long ab=0;int k,ai;
        for(k=0;k<6;k++)ab|=(unsigned long long)p[k+2]<<(k*8);
        ai=(int)((ab>>(index*3))&7);
        if(ai<2)a=p[ai];
        else if(p[0]>p[1])a=((8-ai)*p[0]+(ai-1)*p[1])/7;
        else if(ai<6)a=((6-ai)*p[0]+(ai-1)*p[1])/5;
        else a=ai==7?255:0;
    }
    if(a<100)return 0;
    if(b->format!=14)p+=8;
    c0=p[0]|p[1]<<8;c1=p[2]|p[3]<<8;
    bits=(unsigned long)p[4]|(unsigned long)p[5]<<8|(unsigned long)p[6]<<16|(unsigned long)p[7]<<24;
    colors=(bits>>(index*2))&3;
    {int r0=(c0>>11)*255/31,g0=((c0>>5)&63)*255/63,b0=(c0&31)*255/31;
     int r1=(c1>>11)*255/31,g1=((c1>>5)&63)*255/63,b1=(c1&31)*255/31;
     if(colors==0){r=r0;g=g0;blue=b0;}else if(colors==1){r=r1;g=g1;blue=b1;}
     else if(b->format==14 && c0<=c1){if(colors==3)return 0;r=(r0+r1)/2;g=(g0+g1)/2;blue=(b0+b1)/2;}
     else {int w=colors==2?2:1;r=(w*r0+(3-w)*r1)/3;g=(w*g0+(3-w)*g1)/3;blue=(w*b0+(3-w)*b1)/3;}}
    return blue>120 && g>60 && blue>r+60;
}
static void ak_region(struct bitmap_data *bitmap,int x0,int y0,int x1,int y1,int sx0,int sx1)
{
    struct rasterizer_dynamic_screen_geometry_parameters p;
    struct dynamic_screen_vertex v[4];int i;
    memset(&p,0,sizeof(p));memset(v,0,sizeof(v));
    p.map[0]=bitmap;p.map_scale[0].i=p.map_scale[0].j=1;
    p.map_texture_scale[0].i=p.map_texture_scale[0].j=1;
    for(i=0;i<4;i++) {
        v[i].color=0xffffffff;v[i].position.x=(i%3)?x1:x0;v[i].position.y=i>1?y1:y0;
        v[i].texture_coordinates.x=(real)((i%3)?sx1:sx0)/bitmap->width;
        v[i].texture_coordinates.y=(real)(i>1?y1:y0)/bitmap->height;
    }
    rasterizer_psuedo_dynamic_screen_quad_draw(&p,v);
}
void android_draw_keyboard_background(struct bitmap_data *bitmap)
{
    static struct bitmap_data *last;static long last_offset;static int count,holes[16][2];
    int x,y,start,previous=0;
    if(!bitmap || bitmap->width<640 || bitmap->height<480)return;
    _texture_cache_bitmap_get_hardware_format(bitmap,TRUE,TRUE);
    if(!bitmap->base_address || bitmap->format<14 || bitmap->format>16) {
        rectangle2d r={0,0,480,640};draw_bitmap_in_rect(bitmap,&r,&r,NULL,0xffffffff,NULL,FALSE);return;
    }
    if(last!=bitmap || last_offset!=bitmap->pixels_offset) {
        count=0;last=bitmap;last_offset=bitmap->pixels_offset;
        for(x=0;x<640 && count<16;x++) {
            int present=0;for(y=412;y<442;y++)present|=ak_blue_pixel(bitmap,x,y);
            if(!present)continue;
            start=x;
            do {x++;present=0;for(y=412;y<442 && x<640;y++)present|=ak_blue_pixel(bitmap,x,y);}while(x<640 && present);
            if(x-start>=4 && x-start<=14) {
                int top=442,bottom=412,bands=0,in_band=0,xx;
                for(y=412;y<442;y++) {
                    present=0;for(xx=start;xx<x;xx++)present|=ak_blue_pixel(bitmap,xx,y);
                    if(present){if(!in_band)bands++;if(y<top)top=y;bottom=y;}in_band=present;
                }
                if(bands==2 && bottom-top>=3 && bottom-top<=10) {
                    holes[count][0]=start-1;holes[count++][1]=x+1;
                }
            }
        }
    }
    if(!count) {rectangle2d r={0,0,480,640};draw_bitmap_in_rect(bitmap,&r,&r,NULL,0xffffffff,NULL,FALSE);return;}
    ak_region(bitmap,0,0,640,412,0,640);ak_region(bitmap,0,442,640,480,0,640);
    for(x=0;x<count;x++) {
        ak_region(bitmap,previous,412,holes[x][0],442,previous,holes[x][0]);
        ak_region(bitmap,holes[x][0],412,holes[x][1],442,20,21);previous=holes[x][1];
    }
    ak_region(bitmap,previous,412,640,442,previous,640);
}
