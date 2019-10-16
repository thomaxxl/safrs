import React from 'react'
import './style.css'

class ItemView extends React.Component {

    render() {
        return <pre>{JSON.stringify(this.props, null, 2)}</pre>
    }
}


class ItemInfo extends React.Component {
    /*
        Default ItemInfo viewer, this will be rendered if no viewer is specified for an item
    */

    constructor(props) {
        super(props)
        console.log('ItemInfo', props)
        this.state = { item: null }

        let item_id = this.props.match.params.itemId
        this.props.action.getSingleAction(this.props.objectKey, this.props.match.params.itemId).then(() => {
            let item = this.props.api_data[this.props.objectKey].data.find(item => item.id == item_id)
            this.setState({ item: item })
        })
    }

    render() {

        if (!this.state.item) {
            return <div>No such item</div>
        }
        return <ItemView item={this.state.item} />
    }
}

export {ItemInfo}