var Class = YAHOO.zenoss.Class;

setInnerHTML = YAHOO.zenoss.setInnerHTML;

var isManager = true;
function isDate(ob) {
    if (ob==null) return false;
    if (typeof(ob)=='object'){
        if ('getDate' in ob) return true;
    }
}

var ZenGridLoadingMsg = Class.create();
ZenGridLoadingMsg.prototype = {
    __init__: function(msg) {
        bindMethods(this);
        this.framework = DIV(
            {'class':'zengridload_container'},
            [
            //top row
            DIV({'class':'dbox_tl'},
             [ DIV({'class':'dbox_tr'},
               [ DIV({'class':'dbox_tc'}, null)])]),
            //middle row
            DIV({'class':'dbox_ml'},
             [ DIV({'class':'dbox_mr'},
               [ DIV({'class':'dbox_mc',
                      'id':'zengridload_content'}, msg)])]),
            //bottom row
            DIV({'class':'dbox_bl'},
             [ DIV({'class':'dbox_br'},
               [ DIV({'class':'dbox_bc'}, null)])])
            ]);
        appendChildNodes($('frame'), this.framework);
        this.show();

    },
    getViewportCenter: function() {
        var dims = getViewportDimensions();
        var pos = getViewportPosition();
        return new Coordinates((dims.w/2)+pos.x, (dims.h/2)+pos.y);
    },
    show: function(msg) {
        if (msg) setInnerHTML($('zengridload_content'), msg);
        var p = this.getViewportCenter();
        var d = getElementDimensions(this.framework);
        var pos = new Coordinates(p.x-(d.w/2),p.y-(d.h/2));
        setElementPosition(this.framework, pos);
        showElement(this.framework);
    },
    hide: function() {
        hideElement(this.framework);
    }
}
var ZenGridBuffer = Class.create();

ZenGridBuffer.prototype = {
    __init__: function(url) {
        this.startPos = 0;
        this.size = 0;
        this.rows = new Array();
        this.updating = false;
        this.grid = null;
        this.maxQuery = 60;
        this.totalRows = 0;
        this.numRows = 0;
        this.numCols = 0;
        this.pageSize = 10;
        this.bufferSize = 5; 
        this.marginFactor = 0.2; 
        bindMethods(this);
    },
    tolerance: function() {
        return parseInt(this.bufferSize * this.pageSize * this.marginFactor);
    },
    endPos: function() {return this.startPos + this.rows.length;},
    querySize: function(newOffset) {
        var newSize = 0;
        if (this.totalRows!=0) {
            if (newOffset>=this.totalRows) return 0;
        }
        if (newOffset >= this.startPos) { //appending
            var endQueryOffset = this.maxQuery + this.grid.lastOffset;
            newSize = endQueryOffset - newOffset;
            if(newOffset==0 && newSize < this.maxQuery)
                newSize = this.maxQuery;
        } else { // prepending
            newSize = Math.min(this.startPos - newOffset, this.maxQuery);
        }
        newSize = Math.max(0, newSize);
        newSize = Math.min(newSize, this.maxQuery, this.totalRows?this.totalRows-newOffset:this.maxQuery);
        return newSize;
    },
    queryOffset: function(offset) {
        var newOffset = offset;
        var reverse = this.grid.lastOffset > offset;
        if (offset > this.startPos && !reverse){ 
            newOffset = Math.max(offset, this.endPos()); //appending
        }
        else if (offset > this.startPos && reverse) {
            newOffset = offset - this.maxQuery;
        }
        else if (offset + this.maxQuery >= this.startPos) {
            newOffset = Math.max(this.startPos - this.maxQuery, 0); //prepending

            if (offset-newOffset-this.maxQuery<this.tolerance()) {
                newOffset = Math.min(offset, newOffset + (2*this.tolerance()));
            }
        }
        newOffset = Math.max(0, newOffset); // Disallow negatives
        newOffset = Math.min(newOffset, this.totalRows); // No more than we have
        return newOffset;
    },
    getRows: function(start, count) {
        var bPos = start - this.startPos;
        var ePos = Math.min(bPos+count, this.size);
        var results = new Array();
        for (var i=bPos; i<ePos; i++)
            results.push(this.rows[i]);
        return results;
    },
    isInRange: function(start) {
        var lastRow = Math.min(start + this.pageSize);
        return (start >= this.startPos)&&(lastRow<=this.endPos())&&(this.size!=0);
    },
    update: function(response, start) {
        var newRows = response;
        if (newRows==null) return;
        this.rcvdRows = newRows.length;
        if (this.rows.length==0) { // initial load
            this.rows = newRows;
            this.startPos = start;
        } else if (start > this.startPos) { // appending
            if (this.startPos + this.rows.length < start) {
                this.rows = newRows;
                this.startPos = start;
            } else {
                this.rows = this.rows.concat( newRows.slice(0, newRows.length));
                if (this.rows.length > this.maxQuery) {
                    var fullSize = this.rows.length;
                    this.rows = this.rows.slice(
                        this.rows.length - this.maxQuery, this.rows.length
                    );
                    this.startPos = this.startPos + (fullSize - this.rows.length);
                }
            }
        } else { //prepending
            if (start + newRows.length < this.startPos) {
                this.rows = newRows;
            } else {
                this.rows = newRows.slice(0, this.startPos).concat(this.rows);
                if (this.maxQuery && this.rows.length > this.maxQuery)
                    this.rows = this.rows.slice(0, this.maxQuery)
            }
            this.startPos = start;
        }
        this.size = this.rows.length;
    },
    clear: function() {
        this.rows = new Array();
        this.startPos = 0;
        this.size = 0;
    }
}


var ZenGrid = Class.create();

ZenGrid.prototype = {
    __init__: function(container, url, gridId, buffer, absurl, isHistory,
                       messageCallback) {
        bindMethods(this);
        this.absurl = absurl;
        this.isHistory = isHistory || 0;
        this.message = messageCallback || function(msg){noop()};
        this.container = $(container);
        this.gridId = gridId;
        this.buffer = buffer;
        this.buffer.grid = this;
        this.numRows = 10;
        this.rowHeight = 32;
        this.checkedArray = new Array();
        this.url = this.absurl + '/' + url;
        this.lastparams = this.isHistory?{startdate:$('startdate').value,
                                          enddate:$('enddate').value }:
                          {};
        try {this.lastparams['severity'] = $('severity').value;}catch(e){noop()}
        try {this.lastparams['state'] = $('state').value;}catch(e){noop()}
        try {this.lastparams['filter'] = $('filter').value;}catch(e){noop()}
        this.fields = [];
        this.fieldMapping = {
            //summary: -9,
            //component: +6,
            //eventClass: +2,
            //count: +3
            //firstTime: -1,
            //lastTime: -1
        }
        this.lastOffset = 0;
        this.lastPixelOffset = this.lastPixelOffset || 0;
        var isMSIE//@cc_on=1;
        this.rowSizePlus = this.rowHeight+(isMSIE?3:3);
        this.buildHTML();
        this.selectstatus = 'none';
        this.clearFirst = false;
        this.lock = new DeferredLock();
        this.scrollTimeout = null;
        this.viewportHeight = null;
        this.loadingbox = new ZenGridLoadingMsg('Loading...');
        fieldlock = this.lock.acquire();
        fieldlock.addCallback(this.refreshFields);
        updatelock = this.lock.acquire();
        updatelock.addCallback(bind(function(r){
            var isMSIE//@cc_on=1;
            if (!isMSIE) this.resizeTable();
            this.message('Last updated ' + 
                         getServerTimestamp() + '.');
            if (this.lock.locked) this.lock.release();
        }, this));
        this.addMouseWheelListening();
        connect(this.scrollbar, 'onscroll', this.handleScroll);
        connect(currentWindow(), 'onresize', bind(function(){
            newheight = getViewportDimensions().h;
            if (this.viewportHeight != newheight) {
                this.resizeTable();
            }
        }, this));
    },
    turnRefreshOn: function() {
        var time = $('refreshRate').value;
        this.refreshMgr = new RefreshManager(time, this.refresh);
        var button = $('refreshButton');
        setStyle(button, 
            {'background-image':'url(img/refresh_off.png)'});
        button.onclick = this.turnRefreshOff;
        button.blur();
    },
    turnRefreshOff: function() {
        var button = $('refreshButton');
        try {
            this.refreshMgr.cancelRefresh();
            delete this.refreshMgr;
        } catch(e) { noop(); }
        setStyle(button,
            {'background-image':'url(img/refresh_on.png)'});
        button.onclick = this.turnRefreshOn;
        button.blur();
    },
    setSelectNone: function() {
        this.checkedArray = new Array();
        var cbs = this.viewport.getElementsByTagName('input');
        for (i=0;i<cbs.length;i++) {
            cbs[i].checked=null;
        }
        this.selectstatus = 'none';
    },
    setSelectAll: function() {
        this.checkedArray = new Array();
        var cbs = this.viewport.getElementsByTagName('input');
        for (i=0;i<cbs.length;i++) {
            cbs[i].checked=true;
        }
        this.selectstatus = 'all';
    },
    setSelectAcked: function() {
        this.checkedArray = new Array();
        var cbs = this.viewport.getElementsByTagName('input');
        var rows = this.zgtable.getElementsByTagName('tr');
        for (i=0;i<cbs.length;i++) {
            rowclass = rows[i].className;
            cbs[i].checked=null;
            if (rowclass.match('acked')) {
                cbs[i].checked=true;
            }
        }
        this.selectstatus = 'acked';
    },
    setSelectUnacked: function() {
        this.checkedArray = new Array();
        var cbs = this.viewport.getElementsByTagName('input');
        var rows = this.zgtable.getElementsByTagName('tr');
        for (i=0;i<cbs.length;i++) {
            rowclass = rows[i].className;
            cbs[i].checked=null;
            if (rowclass.match('noack')) {
                cbs[i].checked=true;
            }
        }
        this.selectstatus = 'unacked';
    },
    addMouseWheelListening: function() {
        if (this.container.addEventListener)
                this.container.addEventListener(
                    'DOMMouseScroll', this.handleWheel, false);
        this.container.onmousewheel = this.handleWheel;
    },
    handleWheel: function(event) {
            var delta = 0;
            if (!event) /* For IE. */
                    event = window.event;
            if (event.wheelDelta) { /* IE/Opera. */
                    delta = event.wheelDelta/120;
                    if (window.opera)
                            delta = -delta;
            } else if (event.detail) { /** Mozilla case. */
                    delta = -event.detail/3;
            }
            if (delta)
                    this.scrollTable(delta);
            if (event.preventDefault)
                event.preventDefault();
        event.returnValue = false;
    },
    scrollTable: function(delta) {
        var pixelDelta = this.rowToPixel(delta);
        this.scrollbar.scrollTop -= pixelDelta;
    },
    getColLengths: function() {
        var lens = new Array();
        this.fieldOffsetTotal = 0;
        for (i=0;i<this.fields.length;i++) {
            var field = this.fields[i];
            var offset = this.fieldMapping[field[0]] || 0;
            lens[lens.length] = field[1] + offset;
        }
        return lens
    },
    refreshWithParams: function(params, offset, url) {
        this.buffer.clear();
        if (offset) this.lastOffset = offset;
        this.url = url || this.url;
        update(this.lastparams, params);
        this.refreshTable(this.lastOffset);
    },
    refresh: function() {
        this.buffer.clear();
        this.refreshTable(this.lastOffset);
        this.message('Last updated ' + 
                     getServerTimestamp() + '.');
    },
    query: function(offset) {
        var url = this.url || 'getJSONEventsInfo';
        bufOffset = this.buffer.queryOffset(offset);
        this.lastOffset = offset;
        bufSize = this.buffer.querySize(bufOffset);
        if (bufSize==0) {
             if (this.lock.locked) this.lock.release();
            return;
        }
        var qs = update(this.lastparams, {
            'offset': bufOffset,
            'count': bufSize,
            'getTotalCount': 1
        });
        var isMSIE//@cc_on=1;
        if (isMSIE) {
            qs._dc= new Date().getTime();
        }
        if ('askformore' in this) this.askformore.cancel()
        this.askformore = loadJSONDoc(url, qs);
        this.askformore.addErrback(bind(function(x) { 
            callLater(5, bind(function(){
            this.message('Unable to communicate with the server.');
            this.emptyTable();
            this.killLoading()}, this))
            delete this.askformore;
        }, this));
        this.askformore.addCallback(
         bind(function(r) {
             result = r; 
             this.buffer.totalRows = result[1];
             this.setScrollHeight(this.rowToPixel(this.buffer.totalRows));
             this.buffer.update(result[0], bufOffset);
             delete this.askformore;
             if (this.lock.locked) this.lock.release();
         }, this));
    },
    refreshTable: function(offset) {
        this.showLoading();
        var lastOffset = this.lastOffset;
        //this.lastOffset = offset;
        this.scrollbar.scrollTop = this.rowToPixel(offset);
        var inRange = this.buffer.isInRange(offset);
        var isMSIE//@cc_on=1;
        if (isMSIE) setStyle(this.zgtable, 
            {'table-layout':'fixed'}
        );
        if (inRange) {
            this.populateTable(this.buffer.getRows(offset, this.numRows));
            if (offset > lastOffset) {
                if (offset+this.buffer.pageSize < 
                    this.buffer.endPos()-this.buffer.tolerance()) return;
            } else if (offset < lastOffset) {
                if (offset > this.buffer.startPos + this.buffer.tolerance()) 
                    return;
                if (this.buffer.startPos==0) return;
            } else return;
        }
        if (offset >= this.buffer.totalRows && this.buffer.rcvdRows) return;
        d = this.lock.acquire();
        d.addCallback(bind(function() {
          this.query(offset);
        }, this));
        popLock = this.lock.acquire();
        popLock.addCallback(bind(function() {
            if (this.lock.locked) this.lock.release();
            this.updateStatusBar(offset);
            try {
                myrows = this.buffer.getRows(offset, this.numRows);
                this.populateTable(myrows);
            } catch(e) { 
                console.log("We have a problem of sorts.");
            }
            this.killLoading();
        }, this));
    },
    getBlankRow: function(indx) {
        var i = String(indx);
        cells = map(function(x) {return TD({
            'class':'cell',
            'id':x[0]+'_'+i}, 
                DIV({'class':'cell_inner'}, null))},
            this.fields);
        return TR({'class':'zengrid_row'}, cells);
    },
    populateRow: function(row, data) {
        var stuffz = row.getElementsByTagName('div')
        for (i=0;i<stuffz.length-1;i++) {
            setInnerHTML(stuffz[i], data[i]);
        }
        setElementClass(stuffz[stuffz.length-1], 'event_detail');    

        if (isManager) {
            var cb = '<input type="checkbox" style="visibility:hidden"/>';
            setInnerHTML(stuffz[0], cb);
            setStyle(stuffz[0], {'width':'20px'});
        }
        setStyle(stuffz[stuffz.length-1], {'width':'32px'});
    },
    getColgroup: function() {
        var widths = this.getColLengths();
        var cols = map(function(w){
            if (parseFloat(w)<3) w=String(3);
            return createDOM( 'col', {width: w+'%'}, null)
        }, widths);
        updateNodeAttributes(cols[0], {width:'0*'});
        var isMSIE//@cc_on=1;
        if (isMSIE) updateNodeAttributes(cols[0], {width:'26px'});
        updateNodeAttributes(cols[cols.length-1], {width:'32'});
        colgroup = createDOM('colgroup', {span:widths.length, height:'32px'}, 
            cols);
        return colgroup;
    },
    connectHeaders: function(cells) {
        for(i=isManager?1:0;i<cells.length;i++) { 
            setStyle(cells[i], {'cursor':'pointer'});
            connect(cells[i], 'onclick', this.toggleSortOrder);
        }
        setStyle(cells[isManager?1:0], {
            'background':'#aaa url(img/arrow.u.gif) right no-repeat',
            'color':'black'
        });
    },
    toggleSortOrder: function(e) {
        var cell = e.src();
        var f = cell.getElementsByTagName('div')[0].innerHTML;
        var headcells = this.headers.getElementsByTagName('td');
        var clearcell = function(cell){setStyle(cell,{'background':'','color':''})}
        map(clearcell, headcells);
        if (this.lastparams) {
            switch(this.lastparams['orderby']) {
                case (f + ' ASC'):
                    setStyle(cell, {
                        'background':'#aaa url(img/arrow.d.gif) right no-repeat',
                        'color':'black'
                    });
                    this.refreshWithParams({'orderby': f + ' DESC'});
                    return;
                case (f + ' DESC'):
                    clearcell(cell);
                    setStyle(headcells[isManager?1:0], {
                        'background':'#aaa url(img/arrow.u.gif) right no-repeat',
                        'color':'black'
                    });
                    this.refreshWithParams({'orderby': ''});
                    return;
                default:
                    setStyle(cell, {
                        'background':'#aaa url(img/arrow.u.gif) right no-repeat',
                        'color':'black'
                    });
                    this.refreshWithParams({'orderby':f + ' ASC'});
                    return;
            }
        } else {
            setStyle(cell, {
                'background':'#aaa url(img/arrow.u.gif) right no-repeat',
                'color':'black'
            });
            this.refreshWithParams({'orderby':f + ' ASC'});
        }
    },
    refreshWidths: function() {
        var abswidths = [];
        forEach(this.headers.getElementsByTagName('td'), function(cell){
            var myw = getElementDimensions(cell).w;
            abswidths.push(myw);
        });
        this.abswidths = abswidths;
    },
    refreshFields: function() {
        var updateColumns = bind(function() {
            var numcols = this.fields.length;
            var fields = map(function(x){return x[0]}, this.fields);
            this.colgroup = swapDOM(this.colgroup, this.getColgroup());
            this.headcolgroup = swapDOM(this.headcolgroup, this.getColgroup());
            var headerrow = this.getBlankRow('head');
            replaceChildNodes(this.headers.getElementsByTagName('tbody')[0],
                headerrow);
            this.populateRow(headerrow, fields);
            cells = this.headers.getElementsByTagName('td');
            this.connectHeaders(cells);
            this.refreshWidths();
            this.setTableNumRows(this.numRows);
            if (this.lock.locked) this.lock.release();
        }, this);
        fieldparams = {}; 
        if (this.isHistory) fieldparams['history'] = 1;
            var x = loadJSONDoc(this.absurl + '/getJSONFields', fieldparams);
        x.addCallback(bind(function(r){
            this.fields=concat(r,[['&nbsp;','']]);
            if (isManager) this.fields = concat([['&nbsp;','']], this.fields);
            updateColumns();
        }, this));
    },
    emptyTable: function() {
        this.setTableNumRows(0);
    },
    clearTable: function() {
        table = this.zgtable;
        var cells = getElementsByTagAndClassName('div', 'cell_inner', table);
        var rows = table.getElementsByTagName('tr');
        for (i=0;(cell=cells[i]);i++){
            setInnerHTML(cell, '');
        }
        forEach(rows, function(row){
                forEach(['zenevents_5_noack', 'zenevents_4_noack', 
                         'zenevents_3_noack', 'zenevents_2_noack',
                         'zenevents_1_noack', 'zenevents_0_noack'],
                         function(className){ 
                            removeElementClass(row, className); 
                        });
                });
    },
    setTableNumRows: function(numrows) {
        this.rowEls = map(this.getBlankRow, range(numrows));
        replaceChildNodes(this.output, this.rowEls);
        setElementDimensions(this.viewport,
            {h:parseInt(this.rowToPixel(numrows))}
        );
        var scrollHeight = parseInt(this.rowToPixel(numrows));
        if (scrollHeight <= 0) 
            setElementDimensions(this.scrollbar, {h:0});
        else if (scrollHeight<=getElementDimensions(this.zgtable).h-2) {
            setStyle(this.scrollbar, {'display':'none'});
        } else {
            setElementDimensions(this.scrollbar, {h:scrollHeight});
        }
    },
    shouldBeChecked: function(evid, klass) {
        if (this.checkedArray[evid]=='checked') 
            return true;
        if (this.checkedArray[evid]=='blank')
            return false;
        switch (this.selectstatus) {
            case 'none': return false;
            case 'all': return true;
            case 'acked':
                return !!klass.match('acked');
            case 'unacked':
                return !!klass.match('noack');
        }
        return false;
    },
    populateTable: function(data) {
        var tableLength = data.length > this.numRows ? 
            this.numRows : data.length;
        if (tableLength != this.rowEls.length){ 
            //this.clearTable();
            this.setTableNumRows(tableLength);
        }
        var rows = this.rowEls;
        disconnectAllTo(this.markAsChecked);
        this.refreshWidths();
        for (var numrows=0;numrows<rows.length&&numrows<data.length;numrows++) {
            var mydata = data[numrows];
            setElementClass(rows[numrows], mydata[mydata.length-1])
            var evid = mydata[mydata.length-2];
            var chkbox = '<input type="checkbox" name="evids:list" ';
            if (this.shouldBeChecked(evid, mydata[mydata.length-1])) 
                chkbox+='checked ';
            chkbox += 'value="'+evid+'" id="'+evid+'"/>';
            var yo = rows[numrows].getElementsByTagName('td');
            var divs = rows[numrows].getElementsByTagName('div');
            var firstcol = yo[0];
            if (isManager) {
                mydata = concat([''],mydata);
                setInnerHTML(divs[0], chkbox);
                setStyle(divs[0], {'width':'20px'});
                connect($(evid), 'onclick', this.markAsChecked);
            }
            var lastcol = yo[yo.length-1];
            setElementClass(divs[yo.length-1], 'event_detail');    
            disconnectAll(divs[yo.length-1]);
            var geteventwindow = function(zeml, evidl) {
                return function() { eventWindow(zeml, evidl) }
            }
            connect(divs[yo.length-1], 'onclick', 
                    geteventwindow(this.absurl, evid));
            divs[yo.length-1].title = "View detailed information" + 
                " about this event."
            for (var j=isManager?1:0;j<yo.length-1;j++) {
                var cellwidth = this.abswidths[j] - 9;
                setInnerHTML(divs[j], unescape(mydata[j]));
                yo[j].title = scrapeText(divs[j]);
                setStyle(divs[j], {'width':cellwidth+'px'});
            }

        }
        this.killLoading();
        connectCheckboxListeners();
    },
    getTotalRows: function() {
        cb = bind(function(r) {
            this.buffer.totalRows = r;
            this.setScrollHeight(this.rowToPixel(this.buffer.totalRows));
            if (this.lock.locked) this.lock.release();
        }, this);
        d = loadJSONDoc('getEventCount');
        d.addCallback(cb);
    },
    getHeaderWidths: function() {
        var myws = new Array();
        for (i=0;i<this.fields.length;i++) {
            var width = this.fields[i][0].length * this.fontProportion * 12;
            myws[myws.length] = width;
        }
        return myws
    },
    buildHTML: function() {
        var getId = function(thing) { 
            return "zg_" + thing + "_" + this.gridId }
        getId = bind(getId, this);
        this.scrollbar = DIV(
            {id : getId('scroll')},
            DIV({style: 'height:1000px;'}, null)
        );
        this.output = TBODY( {id: getId('output')}, null);
        this.headcolgroup = createDOM('colgroup', null, null);
        this.colgroup = createDOM( 'colgroup', 
            {style: 'height:'+this.rowHeight+'px'}, null );
        this.zgtable = TABLE( {id: getId('table'),
            cellspacing:0, cellpadding:0}, [
            THEAD(null, null),
            this.colgroup,
            this.output,
            TFOOT(null, null)
        ]);
        this.viewport = DIV( {id: getId('viewport')}, this.zgtable );
        this.statusBar = DIV( {id:getId('statusbar'), 'class':'zg_statusbar'}, 
            SPAN({id:'currentRows'}, String(0+1 +'-'+ parseInt(parseInt(0)+parseInt(this.numRows)) +  ' of ' + this.buffer.totalRows)),
        [   'Select:  ',
            UL(null,
            [
                LI({'id':'setSelectAll'}, 'All'),
                LI({'id':'setSelectNone'}, 'None'),
                LI({'id':'setSelectAcked'}, 'Acknowledged'),
                LI({'id':'setSelectUnacked'}, 'Unacknowledged')
            ])
        ]
        );
        this.headers = TABLE( {id: getId('headers'), 'class':"zg_headers",
            cellspacing:0, cellpadding:0}, [
            this.headcolgroup,
            TBODY(null, null)
        ]);
        this.innercont = DIV( {id:getId('innercont')}, 
            [this.viewport, this.scrollbar]);
        setStyle(this.zgtable, {
            'width': '100%',
            'border': 'medium none',
            'background-color':'#888',
            'padding':'0',
            'margin':'0'
        });
        var isMSIE//@cc_on=1;
        setStyle(this.headers, {
            'width':isMSIE?'96%':'98%'
        });
        setStyle(this.innercont, {
            'width':'100%'

        });
        setStyle(this.viewport, {
            'width':isMSIE?'96%':'98%',
            'height':this.rowToPixel(this.numRows)+'px',
            'overflow':'hidden',
            'float':'left',
            'border':'1px solid black',
            'border-right':'medium none',
            'border-bottom':'medium none'
        });
        addElementClass(this.viewport, 'leftfloat');
        setStyle(this.scrollbar, 
            { //'border': '1px solid black',
              'border-left': 'medium none',
              'overflow': 'auto',
              'z-index':'300',
              'position': 'relative',
              'left': '-3px',
              'width': '19px',
              'height': this.rowToPixel(this.numRows)+'px' 
        });
        var scrollHeight = this.rowToPixel(this.buffer.totalRows);
        this.setScrollHeight(scrollHeight);
        appendChildNodes(this.container, this.statusBar, this.headers, this.innercont);
        connect('setSelectNone', 'onclick', this.setSelectNone);
        connect('setSelectAll', 'onclick', this.setSelectAll);
        connect('setSelectAcked', 'onclick', this.setSelectAcked);
        connect('setSelectUnacked', 'onclick', this.setSelectUnacked);
    },

    setScrollHeight: function(scrlheight) {
        setStyle(this.scrollbar, {'display':'block'});
        setStyle(this.scrollbar.getElementsByTagName('div')[0],
            {'height':String(parseInt(scrlheight)) + 'px'}
        );
        var isMSIE//@cc_on=1;
        if (isMSIE)
            setStyle(this.scrollbar, {'height':this.rowToPixel(this.numRows)+'px'});
    },
    rowToPixel: function(row) {
        return row * (this.rowSizePlus);
    },
    pixelToRow: function(pixel) {
        var prow = parseInt(pixel/(this.rowSizePlus));
        return Math.max(0, prow);
    },
    scrollToPixel: function(pixel) {
        var diff = this.lastPixelOffset-pixel;
        if (diff==0.00 && pixel!=this.scrollbar.height) return;
        var sign = Math.abs(diff)/diff;
        pixel = sign<0?
        Math.ceil(pixel/(this.rowSizePlus))*(this.rowSizePlus):
        Math.floor(pixel/(this.rowSizePlus))*(this.rowSizePlus);
        var newOffset = this.pixelToRow(pixel);
        this.updateStatusBar(newOffset);
        if (this.scrollDeferred) this.scrollDeferred.cancel();
        this.scrollDeferred = callLater(0.1, method(this, function() {
            this.refreshTable(newOffset);
            this.scrollDeferred = null;
        }));
        this.lastPixelOffset = pixel;
    },
    handleScroll: function() {
        this.scrollToPixel(this.scrollbar.scrollTop||0)
    },
    refreshFromFormElement: function(e) {
        node = e.src();
        id = node.id;
        params = {};
        if (!!node.value) params[id] = node.value;
        this.refreshWithParams(params)
    },
    LSTimeout: null,
    doEventLivesearch: function(e) {
        var filters = e.src().value;
        switch (e.key().string) {
            case 'KEY_TAB':
            case 'KEY_ENTER':
                clearTimeout(this.LSTimeout);
                this.refreshWithParams({filter:filters});
                return;
            case 'KEY_ESCAPE':
            case 'KEY_ARROW_LEFT':
            case 'KEY_ARROW_RIGHT':
            case 'KEY_HOME':
            case 'KEY_END':
            case 'KEY_SHIFT':
            case 'KEY_ARROW_UP':
            case 'KEY_ARROW_DOWN':
                return;
        }
        clearTimeout(this.LSTimeout);
        this.LSTimeout = setTimeout(
        bind(
        function () {
            this.refreshWithParams({filter:filters})
        }, this),
        500);
    },
    updateStatusBar: function(rownum) {
        setInnerHTML($('currentRows'), rownum+1 + '-' +
            parseInt(parseInt(rownum)+
            Math.min(parseInt(this.numRows), parseInt(this.buffer.totalRows))
        ) + ' of ' + this.buffer.totalRows);
    },
    markAsChecked: function(e) {
        var node = e.src();
        this.checkedArray[node.value] = node.checked?'checked':'blank';
    },
    showLoading: function() {
        if (this.isLoading) clearTimeout(this.isLoading);
        this.isLoading = setTimeout( bind(function() {
            this.loadingbox.show();
        }, this), 500);
    },
    killLoading: function() {
        if (this.isLoading) clearTimeout(this.isLoading);
        this.loadingbox.hide();
    },
    resizeTable: function() {
        var maxTableBottom = getViewportDimensions().h +
            getViewportPosition().y;
        var topOfRows = getElementPosition(this.viewport).y;
        var bottomMargin = 20;
        var roomToWorkWith = maxTableBottom - topOfRows - bottomMargin;
        var maxRows = Math.floor(roomToWorkWith/this.rowSizePlus);
        var newNumRows = this.buffer.totalRows ?
                         Math.min(maxRows, this.buffer.totalRows) :
                         maxRows;
        this.numRows = newNumRows;
        this.setTableNumRows(newNumRows);
        this.refreshTable(this.lastOffset);
        this.updateStatusBar(this.lastOffset);
        this.viewportHeight = getViewportDimensions().h;
    },
    deleteBatch: function() {
        var url = this.absurl + '/manage_deleteBatchEvents';
        var selectstatus = this.selectstatus;
        var goodevids = [];
        var badevids = [];
        for (var evid in this.checkedArray) {
            if (this.checkedArray[evid]=='checked') goodevids.push(evid);
            else badevids.push(evid);
        }
        qs = {  'selectstatus':selectstatus, 
                'goodevids':goodevids,
                'badevids':badevids         }
        qs = update(qs, this.lastparams);
        d = doXHR(url, {queryString:qs}); 
        d.addCallback(bind(
            function(r) { 
                this.buffer.clear();
                this.refreshTable(this.lastOffset);
                this.setSelectNone();
                YAHOO.zenoss.Messenger.checkMessages();
            }, this));
    },
    undeleteBatch: function() {
        var url = this.absurl + '/manage_undeleteBatchEvents';
        var selectstatus = this.selectstatus;
        var goodevids = [];
        var badevids = [];
        for (var evid in this.checkedArray) {
            if (this.checkedArray[evid]=='checked') goodevids.push(evid);
            else badevids.push(evid);
        }
        qs = {  'selectstatus':selectstatus, 
                'goodevids':goodevids,
                'badevids':badevids         }
        qs = update(qs, this.lastparams);
        d = doXHR(url, {queryString:qs}); 
        d.addCallback(bind(
            function(r) { 
                this.buffer.clear();
                this.refreshTable(this.lastOffset);
                this.setSelectNone();
                YAHOO.zenoss.Messenger.checkMessages();
            }, this));

    },
    acknowledgeBatch: function() {
        var url = this.absurl + '/manage_ackBatchEvents';
        var selectstatus = this.selectstatus;
        var goodevids = [];
        var badevids = [];
        for (var evid in this.checkedArray) {
            if (this.checkedArray[evid]=='checked') goodevids.push(evid);
            else badevids.push(evid);
        }
        qs = {  'selectstatus':selectstatus, 
                'goodevids':goodevids,
                'badevids':badevids         }
        qs = update(qs, this.lastparams);
        this.showLoading();
        d = doXHR(url, {queryString:qs}); 
        d.addCallback(bind(
            function(r) { 
                this.buffer.clear();
                this.refreshTable(this.lastOffset);
                this.setSelectNone();
                YAHOO.zenoss.Messenger.checkMessages();
            }, this));
    }
}
