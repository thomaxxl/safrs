import React from 'react'
import './style.css'

class ItemView extends React.Component {

    render() {
        return <pre>{JSON.stringify(this.props, null, 2)}</pre>
    }
}


class ItemInfo extends React.Component {

    constructor(props) {
        super(props)
        this.state = { item: null }

        let item_id = this.props.match.params.itemId
        this.props.action.getSingleAction(this.props.objectKey, this.props.match.params.itemId).then(() => {
            for (let item of this.props.api_data[this.props.objectKey].data) {
                if (item.id === item_id) {
                    this.setState({ item: item })
                    break;
                }
            }
        })
    }

    render() {

        if (!this.state.item) {
            return <div>No such item</div>
        }
        return <ItemView item={this.state.item} />
    }
}

export default ItemInfo