import React from 'react'

function cellFormatter(cell) {

    return <strong>{ cell }</strong>
}

let FormatterList = { cellFormatter : cellFormatter }

export default FormatterList