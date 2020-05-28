# Overview

This script summarizes orders from a squarespace inventory into a read-only HTML summary table that is automatcally opened in a web browser.

By downloading the included Python file, simply add your API key and the URL to your squarspace site. The tool will query all pending orders by the date specified in the pop-up window.

The summary table will loop through the types of custom meta data specified in check out (e.g. if there are orders that are specified for "delivery" or "take out" and list those orders by the custom meta data fields.

Alternatively, there is an "override" option that will query ALL pending orders.

Finally, the item quantities are grouped in the final table, to show the number of each item that is PENDING for the date specified.
