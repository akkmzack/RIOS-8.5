var placeKeeper=new PlaceKeeper();function confirmRemove(g,e,c,a,b,f,d,h){return function(l,n,k){var i,j,m=k.getAttribute(c);if(m===h){return}i=document.createElement("a");i.setAttribute("href","");if(g){setElementClass(i,g)}i.onclick=function(){var p,t,s,r,o,q="";p={};p[e]=m;t=b.concat([p]);s="remove";if(Y.Lang.isString(f)){s=f}r=s.charAt(0).toUpperCase()+s.substr(1);if(Y.Lang.isFunction(d)){q=d.call(this,k)}else{if(Y.Lang.isString(d)){q=d}else{q="Are you sure you want to "+s.toLowerCase()+" "+m+"?"}}o=new RBT.Dialog({affinity:RBT.Dialog.AFFINITY_SE,alignNode:i,content:q,buttons:[{label:r,clickFn:function(){this.destroy();a.apply(this,t)}},{label:"Cancel",clickFn:RBT.Dialog.dismiss}]});o.render();return false};j=document.createElement("img");j.setAttribute("src","/images/icon_trash2.png");j.setAttribute("border","0");j.setAttribute("id",l.name+"_remove_"+m);i.appendChild(j);n.appendChild(i)}}function veRefreshLater(a){a=Y.Lang.isNumber(a)||5000;Y.later(a,null,function(){window.location.reload()})}function veHandleEnterKey(d,e,b,a,f){var c=Y.one(e);a=a||[];f=f||null;d.on("key",function(h){var g;h.preventDefault();if(c){RBT.Validator.validateForm(c);g=c.getData("RBT.Validator");if(g&&Y.Object.size(g.invalidFields)>0){return}}b.apply(f,a)},"down:13",Y)}function veCreateActionDialog(g){var f,d,a,e,c={affinity:RBT.Dialog.AFFINITY_SW,actionButtonText:"Add",actionArgs:[],actionContext:null,cancelText:"Cancel"};Y.mix(c,g,true);function b(j){var i=d.get("actionFunc"),h=d.get("actionArgs"),k=d.get("actionContext");if(j){j.preventDefault()}d.hide();i.apply(k,h)}f=[{label:c.cancelText,clickFn:function(h){h.preventDefault();this.hide()}}];if(Y.Lang.isString(c.actionButtonText)){f.unshift({label:c.actionButtonText,clickFn:b})}c.buttons=f;d=new RBT.Dialog(c).render();d.get("boundingBox").setStyle("zIndex",999);srcNode=Y.one(c.srcNode);if(Y.Lang.isString(c.actionButtonText)){srcNode.one('input[type=submit][value="'+c.actionButtonText+'"]').set("id",srcNode.get("id")+"_actionButton")}srcNode.one('input[type=submit][value="'+c.cancelText+'"]').set("id",srcNode.get("id")+"_cancelButton");if(c.actionFunc){d.set("actionFunc",c.actionFunc)}if(c.actionArgs){d.set("actionArgs",c.actionArgs)}if(c.actionContext){d.set("actionContext",c.actionContext)}if(Y.Lang.isString(c.actionButtonText)){a=d.get("contentBox").one('input[value="'+c.actionButtonText+'"]');e=a.get("form");if(e){RBT.Validator.addButtonValidation(a)}veHandleEnterKey(d.get("contentBox").all("input[type=text], input[type=password]"),e,b)}return d}function veShowActionDialog(b,a){a=a||{};if(a.alignNode){b.set("alignNode",a.alignNode)}if(a.actionFunc){b.set("actionFunc",a.actionFunc)}if(a.actionArgs){b.set("actionArgs",a.actionArgs)}if(a.actionContext){b.set("actionContext",a.actionContext)}b.show();b.get("contentBox").one("input").focus()}function veTdAttrStyle(a,b){return function(f,h,e){var g=e.getAttribute(a)||"",c=e.getAttribute(b)||"",d=Y.one(h);d.appendChild(Y.Node.create(g));d.addClass(c)}}function veAJAXSubmit(e){var a,b,g,d,h={url:"/mgmt/xmldata",httpMethod:"POST",callbackArgs:[],liveStatWait:1000,sync:false};Y.mix(h,e,true);h.formEl=Y.one(h.formEl);if(h.liveStat){if(h.sync){h.liveStat.show(h.liveStatMsg,false)}else{a=Y.later(h.liveStatWait,h.liveStat,h.liveStat.show,[h.liveStatMsg,false])}}b={method:h.httpMethod,sync:h.sync,on:{success:h.respMethod?i:j,failure:f}};g=h.data||{};if(h.formEl){d=collectFormFields(h.formEl);Y.mix(g,d,false)}g=k(g,"arg_");b.data=g;Y.io(h.url+"?p="+h.reqMethod,b);function i(p,l){var m,n,o=l.responseXML.documentElement;if("xml"===o.tagName){o=o.firstChild}if(c(o)){return}m=o.firstChild;n={method:h.httpMethod,sync:h.sync,data:{arg_request_id:m.getAttribute("request_id")},on:{success:j,failure:f},"arguments":o};Y.io(h.url+"?p="+h.respMethod,n)}function j(p,m,n){var o,l=m.responseXML.documentElement;if("xml"===l.tagName){l=l.firstChild}if(c(l)){return}if(h.liveStat){if(a){a.cancel()}h.liveStat.hide(true)}if(Y.Lang.isFunction(h.onSuccess)){if(n){o=[n,l].concat(h.callbackArgs)}else{o=[l].concat(h.callbackArgs)}h.onSuccess.apply(this,o)}}function f(m,l){if(h.liveStat){if(a){a.cancel()}h.liveStat.show("Data submission failed: "+l.statusText+" ("+l.status+")",true)}}function c(m){var n,l="An Error Occured.";if(m.nodeName==="error"){l=m.firstChild.data}else{if(m.getAttribute("status")==="fail"){l=m.getAttribute("errorMsg")}else{if(m.nodeName==="result"&&m.firstChild.nodeName==="response"){if(m.firstChild.getAttribute("status")==="success"){return false}else{l=m.firstChild.getAttribute("errorMsg")||"An unknown error occured."}}else{l="Unknown XML response from device: "+m.nodeName}}}if(h.liveStat){if(a){a.cancel()}h.liveStat.show(l,true)}if(h.onFailure){n=[m].concat(h.callbackArgs);h.onFailure.apply(this,n)}return true}function k(n,l){var m={};Y.Object.each(n,function(p,o){m[l+o]=p});return m}}function veReloadPage(a){var b=false;try{b=a.firstChild.getAttribute("_msg")}catch(c){}if(b){window.location=addQueryStringParameter(window.location.toString(),"_msg",b)}else{window.location.reload(true)}}function validateEdgeIdentifier(a){if(!a.match(/^[\.0-9a-zA-Z:\-]{3,}$/)){throw'Granite Edge Identifiers should have 3 or more characters and may only contain letters, numbers, dashes ("-"), periods (".") and colons (":")'}}function fillDiv(f,a,d,e){var c,b;d=Y.Lang.isString(d)?d:"name";f=Y.one(f);a=Y.Array(a);e=e||"None";f.setContent("");if(a.length===0){c="<span>"+e+"</span></br>";b=Y.Node.create(c);f.appendChild(b)}else{Y.each(a,function(h){var g;if(h instanceof Y.Node){g=h.get(d)}else{g=h.getAttribute(d)}c="<span>"+g+"</span></br>";b=Y.Node.create(c);f.appendChild(b)})}}function PlaceKeeper(){var a=Y.QueryString.parse(window.location.search.substr(1));this.delim="|||";this.activetable="activetable";this.page=a.p}PlaceKeeper.prototype.getSaved=function(){return Y.Cookie.getSubs(this.page)};PlaceKeeper.prototype.openTab=function(a){var b=this.getSaved();if(Y.Object.hasKey(b,a.name)){a.switchTo(b[a.name])}};PlaceKeeper.prototype.openTable=function(e,c,a){var d,b;if(e.editAfterLoad!==null){return}d=this.getSaved();if(a&&Y.Object.hasKey(d,this.activetable)&&d[this.activetable]!==e.name){return}if(Y.Object.hasKey(d,e.name+this.delim+c)){b=d[e.name+this.delim+c];e.editAfterLoad=[c,b]}};PlaceKeeper.prototype.saveRow=function(c,b,a){Y.Cookie.setSub(this.page,c.name+this.delim+b,a);Y.Cookie.setSub(this.page,this.activetable,c.name);c.editAfterLoad=[b,a]};PlaceKeeper.prototype.removeRow=function(b,a){Y.Cookie.setSub(this.page,b.name+this.delim+a,"")};PlaceKeeper.prototype.saveTab=function(b,a){Y.Cookie.setSub(this.page,b.name,a)};PlaceKeeper.prototype.saveReportView=function(a){Y.Cookie.setSub(this.page,"reportView",a)};PlaceKeeper.prototype.getReportView=function(){var a=this.getSaved();if(Y.Object.hasKey(a,"reportView")){return a.reportView}};PlaceKeeper.prototype.saveReportSelected=function(a){Y.Cookie.setSub(this.page,"reportSelected",a)};PlaceKeeper.prototype.getReportSelected=function(){var a=this.getSaved();if(Y.Object.hasKey(a,"reportSelected")){return a.reportSelected}};RadioTabControl.prototype.setupPlaceKeeper=function(){Y.each(this.tabs,function(b){var a="#"+this.name+"_"+b[0]+"_title";Y.one(a).on("click",function(){placeKeeper.saveTab(this,b[0])},this)},this);onloadScript+=" placeKeeper.openTab("+this.name+");"};