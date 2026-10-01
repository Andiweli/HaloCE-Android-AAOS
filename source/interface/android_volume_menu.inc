/* Android-only runtime widgets. Original map tags and profile structs stay intact.
   Templates are found by their engine callbacks, not English names or tag paths. */
#define AV_BASE (-4096)
#define AV_CAPACITY 128
#define AV_CHILDREN 24
struct av_node {
    struct ui_widget_definition definition;
    struct ui_widget_child_reference children[AV_CHILDREN];
    struct ui_widget_event_handler_reference events[2];
    long source_tag;
    int caption_style; /* 1: graphic heading, 2: graphic main-menu caption */
    int title_candidate;
    int label; /* 0: original text; 1: title; 2..4: volume labels */
    int category; /* -1 except numeric spinners */
};
static struct av_node av_nodes[AV_CAPACITY];
static int av_count;
static long av_source = NONE, av_button = NONE;
static void const *av_source_address;
extern int android_ui_profile_handler_kind(short function);
extern int host_audio_level(int category);
extern int host_audio_set_level(int category, int value);

static int av_index(long tag) { return tag >= AV_BASE && tag < AV_BASE + av_count ? (int)(tag-AV_BASE) : -1; }
static struct ui_widget_definition *av_definition(long tag) {
    int i=av_index(tag);
    return i>=0 ? &av_nodes[i].definition : (struct ui_widget_definition *)tag_get(UI_WIDGET_DEFINITION_TAG,tag);
}
static char const *av_tag_name(long tag) {
    int i=av_index(tag);
    return tag_get_name(i>=0?av_nodes[i].source_tag:tag);
}
#undef ui_widget_definition_get
#define ui_widget_definition_get(tag) av_definition(tag)
#define tag_get_name(tag) av_tag_name(tag)

static wchar_t const *av_label(int id) {
    if(id==5) {
        switch(XGetLanguage()) {
            case XC_LANGUAGE_GERMAN:return L"BEENDEN";case XC_LANGUAGE_FRENCH:return L"QUITTER";
            case XC_LANGUAGE_SPANISH:return L"SALIR";case XC_LANGUAGE_ITALIAN:return L"ESCI";
            case XC_LANGUAGE_JAPANESE:return L"終了";default:return L"EXIT";
        }
    }
    static wchar_t const *const en[]={L"VOLUMES",L"VOLUME",L"SOUND EFFECTS",L"MUSIC"};
    static wchar_t const *const de[]={L"LAUTSTÄRKE",L"LAUTSTÄRKE",L"SOUNDEFFEKTE",L"MUSIK"};
    static wchar_t const *const fr[]={L"VOLUMES",L"VOLUME",L"EFFETS SONORES",L"MUSIQUE"};
    static wchar_t const *const es[]={L"VOLÚMENES",L"VOLUMEN",L"EFECTOS DE SONIDO",L"MÚSICA"};
    static wchar_t const *const it[]={L"VOLUMI",L"VOLUME",L"EFFETTI SONORI",L"MUSICA"};
    static wchar_t const *const ja[]={L"音量",L"音量",L"効果音",L"音楽"};
    switch(XGetLanguage()) {
        case XC_LANGUAGE_GERMAN:return de[id-1];
        case XC_LANGUAGE_FRENCH:return fr[id-1];
        case XC_LANGUAGE_SPANISH:return es[id-1];
        case XC_LANGUAGE_ITALIAN:return it[id-1];
        case XC_LANGUAGE_JAPANESE:return ja[id-1];
        default:return en[id-1];
    }
}
static int av_kind(struct ui_widget_definition *d,int kind) {
    long i;
    for(i=0;i<d->event_handlers.count;i++) {
        struct ui_widget_event_handler_reference *e=(void *)((struct ui_widget_event_handler_reference *)TAG_BLOCK_ADDRESS(d->event_handlers)+i);
        if(TEST_FLAG(e->flags,_event_handler_run_function_bit) && android_ui_profile_handler_kind(e->function)==kind)return 1;
    }
    return 0;
}
static long av_find_kind(long tag,int kind,int depth) {
    struct ui_widget_definition *d;long i,found;
    if(tag==NONE || depth>12 || av_index(tag)>=0)return NONE;
    d=ui_widget_definition_get(tag);
    if(av_kind(d,kind))return tag;
    for(i=0;i<d->child_widgets.count;i++) {
        struct ui_widget_child_reference *ref=(struct ui_widget_child_reference *)TAG_BLOCK_ADDRESS(d->child_widgets)+i;
        found=av_find_kind(ref->widget_tag.index,kind,depth+1);if(found!=NONE)return found;
    }
    return NONE;
}
/* Search reachable launch targets with a bounded visited set (menus have cycles). */
struct av_search { long visited[256];int count; };
static long av_find_screen(long tag,int kind,int depth,struct av_search *search) {
    struct ui_widget_definition *d;long i,found;
    if(tag==NONE||depth>16||av_index(tag)>=0||search->count==256)return NONE;
    for(i=0;i<search->count;i++)if(search->visited[i]==tag)return NONE;
    search->visited[search->count++]=tag;d=ui_widget_definition_get(tag);
    for(i=0;i<d->event_handlers.count;i++) {
        struct ui_widget_event_handler_reference *e=(struct ui_widget_event_handler_reference *)TAG_BLOCK_ADDRESS(d->event_handlers)+i;
        if(TEST_FLAG(e->flags,_event_handler_open_widget_bit) && e->widget_tag.index!=NONE) {
            if(av_find_kind(e->widget_tag.index,kind,0)!=NONE)return e->widget_tag.index;
            found=av_find_screen(e->widget_tag.index,kind,depth+1,search);if(found!=NONE)return found;
        }
    }
    for(i=0;i<d->child_widgets.count;i++) {
        struct ui_widget_child_reference *ref=(struct ui_widget_child_reference *)TAG_BLOCK_ADDRESS(d->child_widgets)+i;
        found=av_find_screen(ref->widget_tag.index,kind,depth+1,search);if(found!=NONE)return found;
    }
    return NONE;
}
/* Only launches belonging to this item: never follow a sibling's menu graph. */
static int av_opens_color(long tag,int depth) {
    struct ui_widget_definition *d;long i;
    if(tag==NONE||depth>8||av_index(tag)>=0)return 0;
    d=ui_widget_definition_get(tag);
    for(i=0;i<d->event_handlers.count;i++) {
        struct ui_widget_event_handler_reference *e=(struct ui_widget_event_handler_reference *)TAG_BLOCK_ADDRESS(d->event_handlers)+i;
        if(TEST_FLAG(e->flags,_event_handler_open_widget_bit) && av_find_kind(e->widget_tag.index,1,0)!=NONE)return 1;
    }
    for(i=0;i<d->child_widgets.count;i++) {
        struct ui_widget_child_reference *ref=(struct ui_widget_child_reference *)TAG_BLOCK_ADDRESS(d->child_widgets)+i;
        if(av_opens_color(ref->widget_tag.index,depth+1))return 1;
    }
    return 0;
}
static long av_clone(long tag,int category,int depth) {
    struct ui_widget_definition *source;struct av_node *n;long index,i,count;
    if(tag==NONE||depth>12||av_count==AV_CAPACITY)return NONE;
    source=ui_widget_definition_get(tag);index=av_count++;n=&av_nodes[index];memset(n,0,sizeof(*n));
    n->definition=*source;n->category=-1;n->source_tag=tag;
    n->title_candidate=category<0 && source->type==_ui_widget_type_text_box;
    n->definition.event_handlers.count=0;n->definition.event_handlers.address=n->events;
    n->definition.game_data_inputs.count=0;n->definition.search_and_replace_functions.count=0;
    n->definition.conditional_widgets.count=0;n->definition.extended_description_widget.index=NONE;
    n->definition.milliseconds_to_auto_close=0;n->definition.auto_close_fade_time=0;
    n->definition.child_widgets.address=n->children;n->definition.list_flags=0;
    count=source->child_widgets.count;
    if(category>=0 && source->type==_ui_widget_type_spinner_list) {
        n->category=category;count=0;
        n->definition.text_label_string_list.index=NONE;
        n->definition.flags=FLAG(_widget_dpad_leftright_tabs_thru_list_items_bit);
    } else if(category>=0 && source->type==_ui_widget_type_text_box) {
        n->label=category+2;n->definition.text_label_string_list.index=NONE;
    }
    if(av_kind(source,2)) {
        struct ui_widget_child_reference *refs=TAG_BLOCK_ADDRESS(source->child_widgets);
        if(count<3)return NONE;
        n->definition.flags=FLAG(_widget_dpad_updown_tabs_thru_children_bit)|FLAG(_widget_pass_unhandled_events_to_children_bit);
        count=3;
        for(i=0;i<3;i++) {
            int first=av_count;
            n->children[i]=refs[i];
            n->children[i].widget_tag.index=av_clone(refs[i].widget_tag.index,(int)i,depth+1);
            if(n->children[i].widget_tag.index==NONE)return NONE;
            /* Rows must remain focusable after stripping the profile-control
               callbacks. A never-matching handler marks the row as an input
               target; actual left/right input goes to its numeric spinner. */
            av_nodes[first].events[0].event_type=-1;
            av_nodes[first].events[0].widget_tag.index=NONE;
            av_nodes[first].events[0].sound_effect.index=NONE;
            av_nodes[first].definition.event_handlers.count=1;
            av_nodes[first].definition.flags|=FLAG(_widget_pass_unhandled_events_to_children_bit);

        }
    } else {
        if(count>AV_CHILDREN)return NONE;
        for(i=0;i<count;i++) {
            struct ui_widget_child_reference *ref=(struct ui_widget_child_reference *)TAG_BLOCK_ADDRESS(source->child_widgets)+i;
            n->children[i]=*ref;
            if(ref->widget_tag.index==NONE)continue;
            n->children[i].widget_tag.index=av_clone(ref->widget_tag.index,category,depth+1);
            if(n->children[i].widget_tag.index==NONE)return NONE;
        }
    }
    n->definition.child_widgets.count=count;
    return AV_BASE+index;
}
static void av_event(struct av_node *n,int index,int button,int flag,long target) {
    struct ui_widget_event_handler_reference *e=&n->events[index];memset(e,0,sizeof(*e));
    e->event_type=button;e->flags=FLAG(flag);e->widget_tag.index=target;e->sound_effect.index=NONE;
    n->definition.event_handlers.count=index+1;n->definition.event_handlers.address=n->events;
}
/* Bitmap captions have no editable string. Replace the caption widget itself,
   retaining its placement and using the game's loaded UI font. */
static void av_caption(struct av_node *n,int label,long font)
{
    n->caption_style=label==5?2:1;
    n->label=label;n->definition.type=_ui_widget_type_text_box;
    n->definition.background_bitmap.index=NONE;n->definition.text_label_string_list.index=NONE;
    n->definition.text_font.index=font;n->definition.child_widgets.count=0;
    n->definition.text_color.alpha=1;n->definition.text_color.red=1;
    n->definition.text_color.green=1;n->definition.text_color.blue=1;
    n->definition.justification=0;n->definition.text_box_flags=0;
}
static long av_font(void)
{
    long font=tag_loaded('font',"ui\\large_ui");
    if(font==NONE)font=interface_get_tag_index(_interface_font_system);
    return font;
}
static long av_build(long color,long root) {
    struct av_search search={0};long advanced,menu,button,i,title=NONE;int menu_end,start=av_count;short top=32767;
    advanced=av_find_screen(root,2,0,&search);if(advanced==NONE)return NONE;
    menu=av_clone(advanced,-1,0);if(menu==NONE) {av_count=start;return NONE;}menu_end=av_count;
    for(i=start;i<menu_end;i++) {
        struct av_node *n=&av_nodes[i];
        if(n->title_candidate && n->label==0 &&
            n->definition.text_label_string_list.index!=NONE && n->definition.text_font.index!=NONE && n->definition.bounds.y0<top) {
            title=i;top=n->definition.bounds.y0;
        }
    }
    /* Some map editions store the heading as a bitmap, not a text box. */
    {long bitmap_title=NONE;short bitmap_top=32767;
     for(i=start;i<menu_end;i++) {
        struct ui_widget_definition *d=&av_nodes[i].definition;
        if(d->type==_ui_widget_type_container && !d->child_widgets.count &&
           d->background_bitmap.index!=NONE && d->bounds.y1-d->bounds.y0>=12 &&
           d->bounds.x1-d->bounds.x0>=70 && d->bounds.y0<bitmap_top &&
           d->bounds.y0<120) {bitmap_title=i;bitmap_top=d->bounds.y0;}
     }
     if(bitmap_title!=NONE)title=bitmap_title;
    }
    if(title!=NONE)av_caption(&av_nodes[title],1,av_font());
    /* Original map: rows use spinner child offsets 366,373,366. Clone one
       complete numeric template (definition AND child-reference offsets). */
    {struct ui_widget_definition *model=NULL;struct ui_widget_child_reference *model_ref=NULL;
     for(i=start;i<menu_end;i++)if(av_nodes[i].category==0){model=&av_nodes[i].definition;break;}
     for(i=start;i<menu_end;i++) {int j;for(j=0;j<av_nodes[i].definition.child_widgets.count;j++) {
        int c=av_index(av_nodes[i].children[j].widget_tag.index);
        if(c>=0 && av_nodes[c].category==0)model_ref=&av_nodes[i].children[j];
     }}
     if(model && model_ref)for(i=start;i<menu_end;i++) {int j;
        if(av_nodes[i].category>=0) {
            struct ui_widget_definition *d=&av_nodes[i].definition;
            d->bounds=model->bounds;d->horizontal_offset=model->horizontal_offset;d->vertical_offset=model->vertical_offset;
            d->list_header_bounds=model->list_header_bounds;d->list_footer_bounds=model->list_footer_bounds;
            d->list_header_bitmap=model->list_header_bitmap;d->list_footer_bitmap=model->list_footer_bitmap;
        }
        for(j=0;j<av_nodes[i].definition.child_widgets.count;j++) {
            struct ui_widget_child_reference *ref=&av_nodes[i].children[j];int c=av_index(ref->widget_tag.index);
            if(c>=0 && av_nodes[c].category>=0) {ref->horizontal_offset=model_ref->horizontal_offset;ref->vertical_offset=model_ref->vertical_offset;}
        }
     }
    }
    av_nodes[menu-AV_BASE].definition.flags|=FLAG(_widget_pass_unhandled_events_to_children_bit);
    av_event(&av_nodes[menu-AV_BASE],0,_widget_event_b_button,_event_handler_go_back_to_previous_widget_bit,NONE);
    av_event(&av_nodes[menu-AV_BASE],1,_widget_event_back_button,_event_handler_go_back_to_previous_widget_bit,NONE);
    button=av_clone(color,-1,0);if(button==NONE) {av_count=start;return NONE;}
    for(i=button-AV_BASE;i<av_count;i++) if(av_nodes[i].definition.type==_ui_widget_type_text_box) {
        av_nodes[i].label=1;av_nodes[i].definition.text_label_string_list.index=NONE;
    }
    av_event(&av_nodes[button-AV_BASE],0,_gamepad_analog_button_a,_event_handler_open_widget_bit,menu);
    av_source=color;av_source_address=ui_widget_definition_get(color);av_button=button;
    return button;
}
static void av_initialize(struct widget_instance *widget) {
    int i=av_index(widget->definition_tag_index);
    if(i>=0) {
        struct av_node *n=&av_nodes[i];
        if(n->label) {
            wchar_t const *text=av_label(n->label);unsigned long len=ustrlen(text);
            widget->parameters.text_box.text=pool_new_pointer(widget_memory_pool,(len+1)*2,__FILE__,__LINE__);
            if(widget->parameters.text_box.text)csmemcpy(widget->parameters.text_box.text,text,(len+1)*2);
        }
        if(n->category>=0) {
            widget->parameters.list.selected_index=host_audio_level(n->category);
            widget->parameters.list.number_of_items=11;
            widget->parameters.list.item_text=pool_new_pointer(widget_memory_pool,6,__FILE__,__LINE__);
            if(widget->parameters.list.item_text)widget->parameters.list.item_text[0]=0;
        }
    } else if(widget->type==_ui_widget_type_column_list) {
        struct widget_instance *color;
        for(color=widget->child;color;color=color->next) if(av_opens_color(color->definition_tag_index,0)) {
            struct widget_instance *extra,*next=color->next;long tag=av_button;int spacing;
            struct ui_widget_definition *d=ui_widget_definition_get(color->definition_tag_index);
            if(av_source!=color->definition_tag_index||av_source_address!=d)
                tag=av_build(color->definition_tag_index,widget_instance_get_topmost_parent(widget)->definition_tag_index);
            if(tag==NONE)return;
            if(next && av_index(next->definition_tag_index)>=0)return;
            extra=ui_widget_load_by_name_or_tag(NULL,tag,widget,widget->local_player_index,NONE,NONE,NONE);
            if(!extra)return;
            spacing=d->bounds.y1-d->bounds.y0+8;
            if(color->previous) {
                struct ui_widget_definition *p=ui_widget_definition_get(color->previous->definition_tag_index);
                int delta=d->bounds.y0+color->vertical_offset-p->bounds.y0-color->previous->vertical_offset;
                if(delta>0)spacing=delta;
            }
            extra->horizontal_offset=color->horizontal_offset;extra->vertical_offset=color->vertical_offset+spacing;
            extra->previous=color;extra->next=next;color->next=extra;if(next)next->previous=extra;
            for(;next;next=next->next)next->vertical_offset+=spacing;
            { struct widget_instance *item; unsigned short count=0;
              for(item=widget->child;item;item=item->next)count++;
              widget->parameters.list.number_of_items=count; }
            return;
        }
    }
}
static boolean av_adjust(struct widget_instance *widget,int delta) {
    int i=av_index(widget->definition_tag_index);int old,value;
    if(i<0||av_nodes[i].category<0)return FALSE;
    old=host_audio_level(av_nodes[i].category);value=(old+delta+11)%11;
    if(value!=old && !host_audio_set_level(av_nodes[i].category,value)) {
        error(_error_silent,"Unable to save Android profile volumes");return TRUE;
    }
    widget->parameters.list.selected_index=value;
    widget->parameters.list.last_list_tab_direction=delta>0?15:-15;
    return TRUE;
}
static void av_spinner_text(struct widget_instance *widget) {
    int i=av_index(widget->definition_tag_index);int value;wchar_t *text;
    if(i<0||av_nodes[i].category<0)return;
    value=host_audio_level(av_nodes[i].category);text=widget->parameters.list.item_text;
    if(text) {text[0]=value==10?L'1':L'0'+value;text[1]=value==10?L'0':0;text[2]=0;}
}

/* Original descriptions are indexed by original item order, not the expanded
   list position. The new entry deliberately reuses CHANGE NAME's keyboard. */
static struct widget_instance *av_description_text;
int android_volume_description_index(struct widget_instance *list,int fallback)
{
    struct widget_instance *item,*text;int index=0,has_volume=0;
    for(item=list->child;item;item=item->next)if(av_index(item->definition_tag_index)>=0)has_volume=1;
    if(!has_volume)return fallback;
    for(text=list->parameters.list.extended_description?list->parameters.list.extended_description->child:NULL;
        text;text=text->next) if(text->type==_ui_widget_type_text_box)break;
    if(av_description_text==text)av_description_text=NULL;
    for(item=list->child;item;item=item->next) {
        if(item==list->focused_child) {
            if(av_index(item->definition_tag_index)>=0) {av_description_text=text;return 0;}
            return index;
        }
        if(av_index(item->definition_tag_index)<0)index++;
    }
    return fallback;
}
static wchar_t const *av_description(struct widget_instance *widget,wchar_t *buffer,unsigned int capacity)
{
    static wchar_t const *const descriptions[]={
        L"Change the Volume levels.",L"Ändere die Lautstärken.",
        L"Modifiez les niveaux sonores.",L"Cambia los niveles de volumen.",
        L"Modifica i livelli del volume.",L"音量を変更します。"};
    static wchar_t const *const profiles[]={L"Current Profile: ",L"Aktuelles Profil: ",
        L"Profil actuel : ",L"Perfil actual: ",L"Profilo attuale: ",L"現在のプロフィール: "};
    struct player_profile *profile;wchar_t const *parts[4];unsigned int used=0;int language=0,i;
    if(widget!=av_description_text||!capacity)return NULL;
    switch(XGetLanguage()) {
        case XC_LANGUAGE_GERMAN:language=1;break;case XC_LANGUAGE_FRENCH:language=2;break;
        case XC_LANGUAGE_SPANISH:language=3;break;case XC_LANGUAGE_ITALIAN:language=4;break;
        case XC_LANGUAGE_JAPANESE:language=5;break;
    }
    profile=player_ui_get_edit_player_profile();
    parts[0]=descriptions[language];parts[1]=L"\n\n";parts[2]=profiles[language];parts[3]=profile?profile->player_name:L"";
    for(i=0;i<4;i++) {wchar_t const *read=parts[i];while(*read&&used+1<capacity)buffer[used++]=*read++;}
    buffer[used]=0;return buffer;
}
static int av_screen_x(struct widget_instance *w) {int x=0;for(;w;w=w->parent)x+=w->horizontal_offset;return x;}
static int av_screen_y(struct widget_instance *w) {int y=0;for(;w;w=w->parent)y+=w->vertical_offset;return y;}
static void av_move_separator(struct widget_instance *w,int y0,int y1,int x0,int x1,int spacing)
{
    struct widget_instance *child;struct ui_widget_definition *d=ui_widget_definition_get(w->definition_tag_index);
    int y=d->bounds.y0+av_screen_y(w),x=d->bounds.x0+av_screen_x(w);
    if(w->type==_ui_widget_type_container && !w->child && d->background_bitmap.index!=NONE && d->bounds.y1-d->bounds.y0<=12 &&
        d->bounds.x1-d->bounds.x0>=40 && y>=y0 && y<=y1 &&
        x<x1 && x+d->bounds.x1-d->bounds.x0>x0)w->vertical_offset+=spacing;
    for(child=w->child;child;child=child->next)av_move_separator(child,y0,y1,x0,x1,spacing);
}
static void av_finish_layout(struct widget_instance *root,struct widget_instance *w)
{
    struct widget_instance *child;
    for(child=w->child;child;child=child->next) {
        if(av_index(child->definition_tag_index)>=0 && child->previous && child->next &&
            av_index(w->definition_tag_index)<0) {
            struct widget_instance *color=child->previous,*save=child->next;
            struct ui_widget_definition *d=ui_widget_definition_get(color->definition_tag_index);
            struct ui_widget_definition *sd=ui_widget_definition_get(save->definition_tag_index);
            int spacing=child->vertical_offset-color->vertical_offset;
            av_move_separator(root,d->bounds.y1+av_screen_y(color),
                sd->bounds.y0+av_screen_y(save)-spacing,d->bounds.x0+av_screen_x(color),
                d->bounds.x1+av_screen_x(color),spacing);
        }
        av_finish_layout(root,child);
    }
}

