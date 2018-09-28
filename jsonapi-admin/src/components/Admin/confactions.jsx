import React from 'react';
import { connect } from 'react-redux'
import * as analyzejson from './analyzejson'
import { bindActionCreators } from 'redux'

import {
  Header,
  Checkbox,
  Button
} from 'semantic-ui-react'

var stylefloat1 = {
  float: "right",
  marginTop: "10px",
  width: "55%"
}

class Confactions extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      collecitonkey: -1,
      actions: ['CreateAction', 'EditAction', 'DeleteAction', 'InfoAction'],
      checked: [true,true,true,true]
    }
    this.handonClick = this.handonClick.bind(this)
    this.chandleClick = this.chandleClick.bind(this)
  }

  getcollectionname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === key_index) {
        rlt = key
      }
      return true
    })
    return rlt
  }


  handonClick() {
    let data = []
    this.state.actions.map((key, index) => {
      if (this.state.checked[index]) data.push(key)
      return true
    })
    let rdata = {
      collectionId: this.getcollectionname(this.props.index),
      action: data
    }
    this.props.analyze.change_actions(rdata)
  }

  chandleClick(key, value, index) {
    const fake = this.state.checked
    fake[index] = value
    this.setState({checked: fake})
  }

  render() {
    if (this.state.collecitonkey !== this.props.index) {
      this.state.checked = [false, false, false, false]
      if (this.state.collecitonkey === -1) {
        this.state.checked = [true, true, true, true]
      }
      this.setState({collecitonkey: this.props.index})
      Object.keys(this.props.json).map(function(key, index) {
        if (index === this.props.index) {
          this.props.json[key].actions.map((akey, aindex) => {
            this.state.checked[this.state.actions.indexOf(akey)] = true
            return true
          }, this)
        }
        return true
      }, this)
    }
    return (
      <div>
        <Header as='h4'>Actions</Header>
        {
          this.state.actions.map((key, index) => {
            return(
              <div key={index}>
                <Checkbox onClick={(e, {checked}) => this.chandleClick(key, checked, index)} checked={this.state.checked[index]} label={key} />
              </div>
            )
          })
        }
        <Button disabled={Object.keys(this.props.json).length !== 0?false:true} style={stylefloat1} onClick={this.handonClick}>Change config</Button>
      </div>
    )
  }
}

const mapStateToProps = (state) => ({
  json: state.configReducer
})

const mapDispatchToProps = dispatch => ({
  analyze: bindActionCreators(analyzejson, dispatch)
})

export default connect(mapStateToProps, mapDispatchToProps)(Confactions)
