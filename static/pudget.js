if (document.getElementById("expand")){
    document.getElementById("expand").addEventListener("click", function() {
        document.getElementById("extra").classList.toggle("hidden");
    })
}

if (document.getElementById("balance")){
document.getElementById("balance").addEventListener("click", function() {

    var balance_element = document.getElementById("balance");
    url = balance_element.getAttribute("url");

    var cur_balance = balance_element.innerHTML;
    cur_balance = cur_balance.split("\$")[1];

    var form = document.createElement("form");
    form.setAttribute("method", "post");
    form.setAttribute("action","/balance_update");
    form.setAttribute("class","tab_form form-control-sm");

    var bal = document.createElement("input");
    bal.setAttribute("type", "number");
    bal.setAttribute("step", "any");
    bal.setAttribute("max", "999999");
    bal.setAttribute("name", "new_bal");
    bal.setAttribute("class", "sm_num");
    bal.setAttribute("value", cur_balance);

    var sub = document.createElement("input");
    sub.setAttribute("type", "submit");
    sub.setAttribute("value", "update");
    sub.setAttribute("class", "btn btn-sm btn-info tab_but");

    var hidd = document.createElement("input");
    hidd.setAttribute("type", "hidden");
    hidd.setAttribute("name", "source_url");
    hidd.setAttribute("value", url );



   /* var td = document.createElement("td");
    td.setAttribute("colspan", "2");
    td.setAttribute("style","text-align:center");
    td.setAttribute("class","tab_form");
*/
    form.appendChild(bal);
    form.appendChild(sub);
    form.appendChild(hidd);

   // td.appendChild(form);

    var parent = balance_element.parentNode;

    parent.replaceChild(form,balance_element);


})
}